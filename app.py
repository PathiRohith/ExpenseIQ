import json
import uuid
from pathlib import Path

import streamlit as st

from config import UPLOAD_DIR
from database import (
    init_db,
    load_seed_employees,
    get_employees,
    get_employee,
    create_employee,
    save_submission,
    get_submissions,
    get_submission,
    save_override,
    get_overrides,
    get_all_overrides,
)
from reviewer import review_receipt
from rag import is_policy_relevant, retrieve_policies
from reviewer import _call_gemini
from config import POLICY_CHAT_SYSTEM_PROMPT

st.set_page_config(
    page_title="Northwind Expense Review",
    layout="wide",
)

init_db()
load_seed_employees()

st.title("Northwind Expense Review")

page = st.sidebar.selectbox(
    "Navigation",
    [
        "Dashboard",
        "New Submission",
        "History",
        "Override Audit Log",
        "Policy Chat",
    ],
)

# ─────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────
if page == "Dashboard":
    submissions = get_submissions()
    employees = get_employees()

    st.subheader("Overview")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Employees", len(employees))
    with col2:
        st.metric("Submissions", len(submissions))
    with col3:
        verdicts = [json.loads(s["review_json"]).get("verdict", "") for s in submissions]
        flagged = sum(1 for v in verdicts if v.lower() in ("flagged", "rejected"))
        st.metric("Flagged / Rejected", flagged)

    st.subheader("Recent Submissions")
    if submissions:
        display_rows = []
        for s in submissions[:20]:
            review = json.loads(s["review_json"])
            display_rows.append({
                "Employee": s.get("employee_name", s["employee_id"]),
                "Receipt": s["receipt_name"],
                "Category": review.get("category", ""),
                "Verdict": review.get("verdict", ""),
                "Confidence": review.get("confidence", ""),
                "Submitted": s["created_at"],
            })
        st.dataframe(display_rows, use_container_width=True)
    else:
        st.info("No submissions yet.")

# ─────────────────────────────────────────────────────────
# NEW SUBMISSION
# ─────────────────────────────────────────────────────────
elif page == "New Submission":
    employees = get_employees()

    st.subheader("Employee")

    emp_mode = st.radio(
        "Employee selection",
        ["Pick existing employee", "Create new employee"],
        horizontal=True,
    )

    selected_employee = None

    if emp_mode == "Pick existing employee":
        if not employees:
            st.warning("No employees found. Please create one.")
        else:
            employee_names = {
                f"{emp['name']} — Grade {emp['grade']} ({emp['employee_id']})": emp
                for emp in employees
            }
            selected_name = st.selectbox("Select Employee", list(employee_names.keys()))
            selected_employee = employee_names[selected_name]

    else:
        with st.form("create_employee_form"):
            st.markdown("**New Employee Details**")
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("Full Name *")
                new_id = st.text_input(
                    "Employee ID",
                    placeholder="Auto-generated if blank",
                )
                new_grade = st.selectbox("Grade", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
                new_dept = st.text_input("Department *")
            with col2:
                new_title = st.text_input("Job Title")
                new_manager = st.text_input("Manager ID")
                new_home = st.text_input("Home Base (city)")
                new_purpose = st.text_input("Default Trip Purpose")

            submitted = st.form_submit_button("Create Employee")
            if submitted:
                if not new_name or not new_dept:
                    st.error("Name and Department are required.")
                else:
                    emp_id = new_id.strip() if new_id.strip() else f"NW-{uuid.uuid4().hex[:5].upper()}"
                    create_employee(
                        emp_id, new_name, new_grade, new_dept,
                        new_purpose, new_title, new_manager, new_home,
                    )
                    st.success(f"Employee {new_name} created (ID: {emp_id})")
                    selected_employee = get_employee(emp_id)

    st.markdown("---")
    st.subheader("Upload Receipts")

    uploaded_files = st.file_uploader(
        "Upload receipts (PDF, TXT, PNG, JPG)",
        type=["pdf", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    if st.button("Analyse Submission", disabled=(selected_employee is None)):
        if not uploaded_files:
            st.warning("Please upload at least one receipt.")
            st.stop()

        if selected_employee is None:
            st.warning("Please select or create an employee first.")
            st.stop()

        Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

        for uploaded_file in uploaded_files:
            file_path = Path(UPLOAD_DIR) / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            with st.spinner(f"Analysing {uploaded_file.name}…"):
                result = review_receipt(selected_employee, file_path)
                submission_id = save_submission(
                    selected_employee["employee_id"],
                    uploaded_file.name,
                    result,
                )

            st.markdown("---")
            st.subheader(uploaded_file.name)
            st.write(f"**Category:** {result.get('category', '')}")

            verdict = result.get("verdict", "Unknown")
            if verdict.lower() == "compliant":
                st.success(f"✅ {verdict}")
            elif verdict.lower() == "flagged":
                st.warning(f"⚠️ {verdict}")
            else:
                st.error(f"❌ {verdict}")

            st.write(f"**Confidence:** {result.get('confidence', '')}%")
            st.write(result.get("reasoning", ""))
            st.caption(f"📌 *{result.get('policy_quote', '')}*")
            st.caption(f"Source: {result.get('policy_source', '')}")

            # Inline override
            with st.expander("Override this verdict"):
                override_verdict = st.selectbox(
                    "New verdict",
                    ["Compliant", "Flagged", "Rejected"],
                    key=f"ov_verdict_{submission_id}",
                )
                override_comment = st.text_area(
                    "Comment (required)",
                    key=f"ov_comment_{submission_id}",
                )
                if st.button("Save Override", key=f"ov_btn_{submission_id}"):
                    if not override_comment.strip():
                        st.error("A comment is required to override a verdict.")
                    else:
                        save_override(
                            submission_id,
                            original_verdict=verdict,
                            new_verdict=override_verdict,
                            comment=override_comment.strip(),
                        )
                        st.success("Override saved and audited.")

# ─────────────────────────────────────────────────────────
# HISTORY
# ─────────────────────────────────────────────────────────
elif page == "History":
    submissions = get_submissions()

    st.subheader("Submission History")

    if not submissions:
        st.info("No submission history found.")
    else:
        for row in submissions:
            review = json.loads(row["review_json"])
            employee_name = row.get("employee_name") or row["employee_id"]
            verdict = review.get("verdict", "Unknown")

            icon = "✅" if verdict.lower() == "compliant" else ("⚠️" if verdict.lower() == "flagged" else "❌")

            with st.expander(
                f"{icon} {row['receipt_name']}  |  {employee_name}  |  {row['created_at']}"
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Employee:** {employee_name} ({row['employee_id']})")
                    st.write(f"**Category:** {review.get('category', '')}")
                    st.write(f"**Verdict:** {verdict}")
                    st.write(f"**Confidence:** {review.get('confidence', '')}%")
                with col2:
                    st.write(review.get("reasoning", ""))
                    st.caption(f"📌 *{review.get('policy_quote', '')}*")
                    st.caption(f"Source: {review.get('policy_source', '')}")

                # Show any overrides
                overrides = get_overrides(row["submission_id"])
                if overrides:
                    st.markdown("**Override history:**")
                    for ov in overrides:
                        st.info(
                            f"**{ov['original_verdict']} → {ov['new_verdict']}** "
                            f"by {ov['overridden_by']} at {ov['created_at']}: "
                            f"_{ov['comment']}_"
                        )

                # Override form in history
                with st.expander("Add override"):
                    ov_verdict = st.selectbox(
                        "New verdict",
                        ["Compliant", "Flagged", "Rejected"],
                        key=f"hist_ov_v_{row['submission_id']}",
                    )
                    ov_comment = st.text_area(
                        "Comment (required)",
                        key=f"hist_ov_c_{row['submission_id']}",
                    )
                    if st.button("Save Override", key=f"hist_ov_btn_{row['submission_id']}"):
                        if not ov_comment.strip():
                            st.error("A comment is required.")
                        else:
                            save_override(
                                row["submission_id"],
                                original_verdict=verdict,
                                new_verdict=ov_verdict,
                                comment=ov_comment.strip(),
                            )
                            st.success("Override saved.")
                            st.rerun()

# ─────────────────────────────────────────────────────────
# OVERRIDE AUDIT LOG
# ─────────────────────────────────────────────────────────
elif page == "Override Audit Log":
    st.subheader("Override Audit Log")

    all_overrides = get_all_overrides()

    if not all_overrides:
        st.info("No overrides recorded yet.")
    else:
        rows = [
            {
                "Override ID": ov["override_id"],
                "Submission ID": ov["submission_id"],
                "Receipt": ov["receipt_name"],
                "Employee": ov.get("employee_name", ""),
                "Original Verdict": ov["original_verdict"],
                "New Verdict": ov["new_verdict"],
                "Comment": ov["comment"],
                "By": ov["overridden_by"],
                "At": ov["created_at"],
            }
            for ov in all_overrides
        ]
        st.dataframe(rows, use_container_width=True)

# ─────────────────────────────────────────────────────────
# POLICY CHAT
# ─────────────────────────────────────────────────────────
elif page == "Policy Chat":
    st.subheader("Policy Chat")
    st.caption(
        "Ask questions about Northwind's expense policies. "
        "Out-of-scope questions will be declined."
    )

    question = st.text_input("Ask a policy question")

    if st.button("Ask"):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Searching policies…"):
                relevant, best_score, chunks = is_policy_relevant(question)

            if not relevant:
                st.error(
                    "❌ This question doesn't appear to be covered by the "
                    "Northwind policy library. Please contact HR directly."
                )
            else:
                policy_context = "\n\n".join(
                    f"[Source: {c['source']}]\n{c['text']}"
                    for c in chunks
                )

                user_prompt = f"""Policy excerpts:
{policy_context}

User question: {question}"""

                with st.spinner("Generating answer…"):
                    answer = _call_gemini(
                        POLICY_CHAT_SYSTEM_PROMPT,
                        user_prompt,
                        json_mode=False,
                    )

                st.markdown(answer)

                with st.expander("Show retrieved policy excerpts"):
                    for c in chunks:
                        st.caption(f"**{c['source']}** (score: {c['score']:.3f})")
                        st.write(c["text"])
                        st.markdown("---")

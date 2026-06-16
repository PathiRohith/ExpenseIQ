# 🧾 ExpenseIQ

> An AI-powered expense receipt compliance reviewer that reads receipts, retrieves relevant company policy via RAG, and delivers structured verdicts — powered by Google Gemini and LlamaIndex.

---

## 📌 Overview

ExpenseIQ automates the review of employee expense receipts against company spending policies. It extracts text from uploaded PDFs, images, or text files, retrieves the most relevant policy sections from a vector knowledge base, and asks Gemini to return a structured compliance verdict — **Compliant**, **Flagged**, or **Rejected** — with confidence score, reasoning, and a cited policy quote.

Managers can override AI verdicts with comments, and a full audit trail is maintained in SQLite. A built-in **Policy Chat** page lets employees ask plain-English questions about the expense policy.

---

## ✨ Features

- 🤖 **AI Receipt Review** — Gemini reads each receipt and evaluates it against retrieved policy chunks
- 📚 **RAG over Policy PDFs** — LlamaIndex + ChromaDB indexes 8 company policy documents for semantic retrieval
- 🔍 **Smart Policy Retrieval** — Query uses employee grade + trip purpose + receipt text for precise context
- 📷 **Multi-format Receipt Support** — PDF (PyMuPDF), images (Tesseract OCR / Gemini Vision), plain text
- ✅ **Structured Verdicts** — JSON output with category, verdict, confidence %, reasoning, policy quote, source
- 🔄 **Manager Override + Audit Log** — Every verdict override is stored with comment and timestamp
- 💬 **Policy Chat** — Employees can ask policy questions; out-of-scope questions are refused
- 🗃️ **SQLite Database** — Employees, submissions, and overrides stored persistently
- 📊 **Dashboard** — Overview metrics and recent submission table
- 🧪 **Evaluation Script** — `evaluate.py` for batch testing verdict accuracy across sample submissions

---

## 🗂️ Project Structure

```
ExpenseIQ/
│
├── app.py                    # Streamlit UI — all 5 pages
├── config.py                 # API keys, model names, paths, system prompts
├── database.py               # SQLite schema, CRUD operations
├── rag.py                    # LlamaIndex vector index build/load + policy retrieval
├── reviewer.py               # Receipt text extraction + Gemini API call + verdict parser
├── evaluate.py               # Batch evaluation over sample submissions
├── requirements.txt          # Python dependencies
├── app.db                    # SQLite database (auto-created)
│
├── chroma_db/                # Persisted LlamaIndex vector store (auto-generated)
│   ├── default__vector_store.json
│   ├── docstore.json
│   ├── index_store.json
│   └── ...
│
└── data/
    ├── policies/             # 8 company expense policy PDFs (RAG knowledge base)
    │   ├── policy1.pdf
    │   ├── policy2.pdf
    │   └── ... (policy3–policy8.pdf)
    │
    ├── submissions/          # Sample test submissions (5 scenarios)
    │   ├── 01_clean_denver/              ✅ Clean — fully compliant trip
    │   ├── 02_clean_boston_conf/         ✅ Clean — conference trip
    │   ├── 03_dinner_over_cap/           ⚠️ Flagged — dinner exceeds policy cap
    │   ├── 04_alcohol_solo_travel/       ❌ Rejected — alcohol on solo travel
    │   └── 05_receipt_mismatch/          ⚠️ Flagged — amounts don't match
    │
    └── uploads/              # Live upload landing folder (runtime)
```

---

## ⚙️ How It Works

```
Receipt Upload (PDF / Image / TXT)
            │
            ▼
    ┌───────────────────┐
    │   extract_text()   │  ← PyMuPDF (PDF) / Tesseract OCR / Gemini Vision (image)
    └────────┬──────────┘
             │
             ▼
    ┌────────────────────────────┐
    │     retrieve_policies()     │
    │  LlamaIndex + ChromaDB      │  ← Query = grade + trip purpose + receipt text
    │  BAAI/bge-small-en-v1.5    │
    └────────┬───────────────────┘
             │  top-3 policy chunks
             ▼
    ┌────────────────────────────┐
    │      Gemini API Call        │
    │  gemini-2.5-flash           │  ← System prompt enforces JSON-only output
    └────────┬───────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────┐
    │  Structured Verdict                      │
    │  {                                       │
    │    "category": "Meals",                  │
    │    "verdict": "Flagged",                 │
    │    "confidence": 87,                     │
    │    "reasoning": "...",                   │
    │    "policy_quote": "...",                │
    │    "policy_source": "policy3.pdf §4.2"  │
    │  }                                       │
    └─────────────────────────────────────────┘
             │
             ▼
    Saved to SQLite → Displayed in Streamlit
```

---

## 🔧 Requirements

### System Requirements

- Python 3.11+
- Tesseract OCR (optional — for image receipts without Gemini Vision fallback)
- Google Gemini API key

### Install Tesseract (optional)

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr

# macOS
brew install tesseract
```

### `requirements.txt`

```txt
streamlit
google-generativeai
llama-index
llama-index-embeddings-huggingface
sentence-transformers
transformers
torch
chromadb
pymupdf
python-dotenv
pydantic
pytesseract
Pillow
```

### Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔑 Environment Setup

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```

Get your API key at [aistudio.google.com](https://aistudio.google.com/app/apikey) — free tier available.

---

## 🚀 Setup & Running

### Step 1 — Unzip the project

```bash
unzip ExpenseIQ.zip
cd ExpenseIQ
```

### Step 2 — Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Add your Gemini API key

```bash
echo "GEMINI_API_KEY=your_key_here" > .env
```

### Step 5 — Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. On first run, LlamaIndex will build the ChromaDB vector index from the policy PDFs (takes ~30 seconds). Subsequent runs load from cache instantly.

---

## 💬 Usage

### Dashboard
Overview of total employees, submissions, and flagged/rejected count. Shows the 20 most recent submissions in a table.

### New Submission
Select an existing employee (pre-seeded from sample data) or create a new one. Upload one or more receipts (PDF, TXT, PNG, JPG). Click **Analyse Submission** to trigger AI review. Results display inline with an optional override panel.

### History
Browse all past submissions with expandable detail cards. Add overrides directly from history view.

### Override Audit Log
Full table of every verdict override — who changed it, when, from what to what, and the required comment.

### Policy Chat
Ask plain-English questions about expense policy. Out-of-scope questions (below relevance threshold) are refused. Shows the retrieved policy excerpts used to generate the answer.

---

## 📋 Sample Submission Scenarios

| Folder | Scenario | Expected Verdict |
|---|---|---|
| `01_clean_denver` | Standard business trip, all within limits | ✅ Compliant |
| `02_clean_boston_conf` | Conference registration + travel + hotel | ✅ Compliant |
| `03_dinner_over_cap` | Dinner at Alinea exceeds per-person limit | ⚠️ Flagged |
| `04_alcohol_solo_travel` | Dinner receipt includes alcohol, solo trip | ❌ Rejected |
| `05_receipt_mismatch` | Submitted amount doesn't match receipt total | ⚠️ Flagged |

---

## 🧩 Key Components

| Component | Library / Tool | Purpose |
|---|---|---|
| LLM | `gemini-2.5-flash` (Google) | Receipt evaluation + policy chat |
| Embeddings | `BAAI/bge-small-en-v1.5` | Policy document vectorization |
| Vector Store | `ChromaDB` via LlamaIndex | Persistent policy retrieval index |
| RAG Framework | `llama-index` | Document loading, chunking, retrieval |
| PDF Parsing | `PyMuPDF (fitz)` | Text extraction from receipt PDFs |
| OCR | `pytesseract` + Gemini Vision fallback | Image receipt text extraction |
| Database | `SQLite` | Employees, submissions, override audit log |
| UI | `streamlit` | Full multi-page web interface |

---

## ⚙️ Configuration (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `MODEL_NAME` | `gemini-2.5-flash` | Gemini model for review + chat |
| `EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | HuggingFace embedding model |
| `CHUNK_SIZE` | `300` | Policy document chunk size (tokens) |
| `CHUNK_OVERLAP` | `30` | Overlap between chunks |
| `TOP_K` | `3` | Number of policy chunks to retrieve |
| `RELEVANCE_THRESHOLD` | `0.30` | Min cosine similarity for policy chat |

---

## 🧪 Running Evaluations

To batch-test the AI reviewer against all sample submissions:

```bash
python evaluate.py
```

This runs all receipts in `data/submissions/` through the review pipeline and prints verdict accuracy metrics.

---

## 🛠️ Troubleshooting

**`GEMINI_API_KEY not set` error**
→ Create a `.env` file with `GEMINI_API_KEY=your_key` in the project root.

**Slow first run**
→ LlamaIndex is building the ChromaDB index from 8 policy PDFs and downloading the embedding model. Should complete in under a minute. Subsequent runs are instant.

**`tesseract is not installed` warning**
→ Image receipts will fall back to Gemini Vision automatically. Install Tesseract if you want local OCR: `sudo apt install tesseract-ocr`.

**Policy Chat refuses all questions**
→ Lower `RELEVANCE_THRESHOLD` in `config.py` from `0.30` to `0.20`.

**Gemini returns non-JSON output**
→ Upgrade to the latest `google-generativeai` package: `pip install -U google-generativeai`.

---

## 📄 License

This project is for educational and research purposes.

---

## 🙌 Acknowledgements

- [Google Gemini](https://ai.google.dev/) for the LLM backbone
- [LlamaIndex](https://www.llamaindex.ai/) for the RAG framework
- [ChromaDB](https://www.trychroma.com/) for the vector store
- [PyMuPDF](https://pymupdf.readthedocs.io/) for PDF text extraction
- [Streamlit](https://streamlit.io/) for the web interface

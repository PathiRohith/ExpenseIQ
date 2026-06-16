import json
import base64
import urllib.request
import urllib.error
import fitz  # PyMuPDF

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from config import (
    GEMINI_API_KEY,
    MODEL_NAME,
    SYSTEM_PROMPT,
)
from rag import retrieve_policies


def extract_text(file_path):
    """Extract text from PDF, TXT, or image receipts."""
    file_path = str(file_path)

    if file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    if file_path.endswith(".pdf"):
        text = []
        pdf = fitz.open(file_path)
        for page in pdf:
            text.append(page.get_text())
        pdf.close()
        return "\n".join(text)

    if file_path.lower().endswith((".png", ".jpg", ".jpeg")):
        # Try pytesseract OCR first
        if TESSERACT_AVAILABLE:
            try:
                img = Image.open(file_path)
                return pytesseract.image_to_string(img)
            except Exception:
                pass

        # Fallback: send image to Gemini Vision
        with open(file_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        ext = file_path.lower().split(".")[-1]
        mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
        mime_type = mime_map.get(ext, "image/jpeg")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Extract all text from this receipt image. Return only the raw text content."},
                    {"inline_data": {"mime_type": mime_type, "data": image_data}}
                ]
            }]
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"[Image OCR failed: {e}]"

    return ""


def _call_gemini(system_prompt, user_prompt, json_mode=True):
    """Call Gemini REST API with automatic JSON-mode fallback."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    )

    def _build_payload(use_json_mime: bool) -> dict:
        generation_config = {"temperature": 0, "maxOutputTokens": 2048}
        if use_json_mime:
            generation_config["responseMimeType"] = "application/json"
        return {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": generation_config,
        }

    def _post(payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Gemini API error {e.code}: {e.reason}\n{body}"
            ) from e

    # First attempt: with responseMimeType if requested
    try:
        result = _post(_build_payload(use_json_mime=json_mode))
    except RuntimeError as first_err:
        if json_mode and "400" in str(first_err):
            # Some models / old API versions don't support responseMimeType;
            # retry without it — the system prompt already asks for JSON.
            result = _post(_build_payload(use_json_mime=False))
        else:
            raise

    return result["candidates"][0]["content"]["parts"][0]["text"]


def review_receipt(employee, receipt_path):
    receipt_text = extract_text(receipt_path)

    retrieval_query = f"""
    Employee Grade: {employee.get('grade')}
    Trip Purpose: {employee.get('trip_purpose')}

    Receipt:
    {receipt_text}
    """

    policies = retrieve_policies(retrieval_query)

    # Cap each policy chunk to 800 chars to keep the prompt small
    policy_context = "\n\n".join(
        f"[Source: {p.get('source', 'policy')}]\n{p['text'][:800]}"
        for p in policies[:3]
    )

    # Truncate receipt text to 1500 chars
    receipt_text_trimmed = receipt_text[:1500] if len(receipt_text) > 1500 else receipt_text

    user_prompt = f"""
Employee Information:
{json.dumps(employee, indent=2)}

Receipt Text:
{receipt_text_trimmed}

Relevant Policy Excerpts:
{policy_context}
"""

    raw = _call_gemini(SYSTEM_PROMPT, user_prompt, json_mode=True)
    clean = raw.strip()

    # Strip markdown fences: ```json ... ``` or ``` ... ```
    if clean.startswith("```"):
        # Drop the opening fence line (e.g. "```json")
        clean = clean.split("\n", 1)[-1]
        # Drop the closing fence
        if "```" in clean:
            clean = clean.rsplit("```", 1)[0]
        clean = clean.strip()

    # Extract the JSON object by finding the outermost { ... }
    # This handles any stray text before or after the JSON block.
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end != -1 and end > start:
        clean = clean[start:end + 1]

    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        # Surface a helpful error with the raw model output for debugging
        raise ValueError(
            f"Gemini returned non-JSON output.\n"
            f"Parse error: {e}\n"
            f"Raw response (first 500 chars):\n{raw[:500]}"
        ) from e

from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Model config ---
# Options: "gemini-2.0-flash" (latest), "gemini-1.5-flash" (stable fallback)
MODEL_NAME = "gemini-2.5-flash"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

# --- RAG config ---
CHUNK_SIZE = 300
CHUNK_OVERLAP = 30
TOP_K = 3

# --- Paths ---
DATA_DIR = BASE_DIR / "data"
POLICY_DIR = DATA_DIR / "policies"
SUBMISSION_DIR = DATA_DIR / "submissions"
UPLOAD_DIR = DATA_DIR / "uploads"

CHROMA_DIR = BASE_DIR / "chroma_db"
DB_PATH = BASE_DIR / "app.db"

SUPPORTED_RECEIPT_TYPES = [".pdf", ".png", ".jpg", ".jpeg", ".txt"]

# --- Policy Chat relevance threshold ---
# Cosine similarity score below this → question is out-of-scope
RELEVANCE_THRESHOLD = 0.30

SYSTEM_PROMPT = """
You are an expense compliance reviewer for Northwind.

Use ONLY the provided policy context to evaluate the receipt.

Return ONLY valid JSON — no markdown, no extra text, no explanation outside the JSON.

Be concise but informative:
- "reasoning": 2-3 sentences, max 60 words
- "policy_quote": the most relevant clause, max 40 words
- "policy_source": document name and section only, max 15 words

{
    "category": "<e.g. Meals, Travel, Accommodation, Ground Transportation>",
    "verdict": "<Compliant | Flagged | Rejected>",
    "confidence": <integer 0-100>,
    "reasoning": "<2-3 sentences, max 60 words>",
    "policy_quote": "<max 40 words>",
    "policy_source": "<max 15 words>"
}
"""

POLICY_CHAT_SYSTEM_PROMPT = """
You are a helpful policy assistant for Northwind's expense policy library.

Answer the user's question based ONLY on the policy excerpts provided.
If the provided excerpts do not contain enough information to answer the question,
say: "I don't have enough policy information to answer that question. Please refer to HR."

Cite the relevant policy section when you answer.
Be concise and factual. Do not make up rules.
"""
import os
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, ".env"))

# ── API Keys ───────────────────────────────────────────────────
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
SECRET_KEY              = os.getenv("SECRET_KEY", "notestack-secret-radical-key-123")

# ── Firebase ───────────────────────────────────────────────────
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "")

# ── University Domains → Names ─────────────────────────────────
ALLOWED_DOMAINS = {
    "rgpv.ac.in":  "RGPV",
    "iitd.ac.in":  "IIT Delhi",
    "nitw.ac.in":  "NIT Warangal",
}

# ── ML Service Tuning ──────────────────────────────────────────
MIN_VERIFICATIONS   = 3
TFIDF_MAX_KEYWORDS  = 10
TFIDF_MAX_SENTENCES = 5

# ── Model Paths ────────────────────────────────────────────────
MODEL_BASE_DIR      = os.path.join(os.path.dirname(__file__), "models")
DIFFICULTY_CLF_PATH = os.path.join(MODEL_BASE_DIR, "difficulty_clf.pkl")

FLAN_T5_MODEL = "google/flan-t5-small"
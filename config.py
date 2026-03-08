import os
from pathlib import Path

# API
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Model used for all Socratic reasoning
REASONING_MODEL = "qwen/qwen3-32b"

CONTEXT_WINDOW = 12

MODES = {
	"gentle": "Curious and collaborative. Asks questions, rarely pushes hard.",
	"rigorous": "Academic. Demands precision, evidence, and logical consistency.",
	"adversarial": "Stress test. Argues the strongest possible opposing position.",
}
DEFAULT_MODE = "rigorous"

# Persistence
DATA_DIR = Path("data")
SESSIONS_FILE = DATA_DIR / "sessions.pkl"

VERSION = "1.1"
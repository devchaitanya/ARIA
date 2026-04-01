import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

REPOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "repos")
os.makedirs(REPOS_DIR, exist_ok=True)

SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rs", ".cpp", ".c", ".h", ".hpp", ".rb", ".php",
    ".cs", ".swift", ".kt", ".scala", ".sh", ".bash",
}

MAX_FILE_SIZE = 100_000  # bytes
MAX_FILES = 200
CLONE_DEPTH = 1

CONFIDENCE_THRESHOLD = 0.7
SIMILARITY_THRESHOLD = 0.85

GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.0-flash"
MISTRAL_MODEL = "mistral-small-latest"

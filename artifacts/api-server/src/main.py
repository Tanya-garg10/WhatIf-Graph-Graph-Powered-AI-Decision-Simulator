import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent / ".env")

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8888"))
    uvicorn.run(app, host="0.0.0.0", port=port)

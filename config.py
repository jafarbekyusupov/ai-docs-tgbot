import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
OLLAMA_BASE_URL = "http://localhost:11434"

import logging
logging.basicConfig(level=logging.INFO)
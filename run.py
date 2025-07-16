from config import TELEGRAM_BOT_TOKEN, GROQ_API_KEY
from document_bot import DocumentBot

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("---- |X| env var for TG BOT TOKEN is either NOT BEING READ or NOT SET ----")
        return
    
    if not GROQ_API_KEY:
        print("---- |X| no GROQ API KEY FOUND, only Ollama will be available ----")
    
    bot = DocumentBot(TELEGRAM_BOT_TOKEN, GROQ_API_KEY)
    bot.run()

if __name__ == "__main__":
    main()
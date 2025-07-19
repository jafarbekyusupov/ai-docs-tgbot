from flask import Flask
import threading

from config import TELEGRAM_BOT_TOKEN, GROQ_API_KEY
from document_bot import DocumentBot

def create_health_server():
    app = Flask(__name__)
    @app.route('/')
    def health():
        return '====== | OK | AI DOC BOT is RUNNINNN ======'    
    return app

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("---- |X| env var for TG BOT TOKEN is either NOT BEING READ or NOT SET ----")
        return
    
    if not GROQ_API_KEY:
        print("---- |X| no GROQ API KEY FOUND, only Ollama will be available ----")
    
    bot = DocumentBot(TELEGRAM_BOT_TOKEN, GROQ_API_KEY)
    if os.environ.get('RENDER'):
        h_app = create_health_server()
        port = int(os.environ.get('PORT', 10000))
        h_thread = threading.Thread(target=lambda: h_app.run(host='0.0.0.0', port=port))
        h_thread.daemon = True
        h_thread.start()
        
    bot.run()

if __name__ == "__main__":
    main()

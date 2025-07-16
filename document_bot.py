import telebot
import logging
from typing import Dict
from document_processor import DocumentProcessor
from ai_processor import AIProcessor
from vector_search import VectorSearch
from bot_handlers import BotHandlers

logger = logging.getLogger(__name__)

class DocumentBot:
    def __init__(self, telegram_token: str, groq_api_key: str = None):
        self.bot = telebot.TeleBot(telegram_token)
        self.doc_procsr = DocumentProcessor()
        self.ai_procsr = AIProcessor(groq_api_key)
        
        self.user_sess: Dict[int, VectorSearch] = {}
        self.user_prefs: Dict[int, Dict] = {}
        
        self.handlers = BotHandlers(
            self.bot, 
            self.doc_procsr, 
            self.ai_procsr, 
            self.user_sess, 
            self.user_prefs
        )
        
        self.setup_handlers()
    
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start', 'help'])
        def handle_start(message):
            self.handlers.handle_start(message)
        
        @self.bot.message_handler(commands=['settings'])
        def handle_settings(message):
            self.handlers.handle_settings(message)
        
        @self.bot.message_handler(commands=['models'])
        def handle_models(message):
            self.handlers.handle_models(message)
        
        @self.bot.message_handler(commands=['status'])
        def handle_status(message):
            self.handlers.handle_status(message)
        
        @self.bot.message_handler(commands=['clear'])
        def handle_clear(message):
            self.handlers.handle_clear(message)
        
        @self.bot.message_handler(content_types=['document'])
        def handle_document(message):
            self.handlers.handle_document(message)
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_question(message):
            self.handlers.handle_question(message)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self.handlers.handle_callback_query(call)
    
    def run(self):
        logger.info("ai document bot started!")
        logger.info(f"available ai services: {self.ai_procsr.get_available_services()}")
        self.bot.polling(none_stop=True)
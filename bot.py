import os
from dotenv import load_dotenv
import logging
import tempfile
from typing import Dict, List, Optional
import PyPDF2
import telebot
from telebot import types
from groq import Groq
import requests
import json
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import re

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
    
    def chat(self, model: str, messages: List[Dict], max_tokens: int = 500, temperature: float = 0.1):
        url = f"{self.base_url}/api/generate"
        
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += f"{msg['content']}\n\n"
            elif msg["role"] == "user":
                prompt += f"{msg['content']}"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "stop": ["</s>", "<|end|>"]
            }
        }
        
        try:
            logger.info(f"sending request to ollama: {url} with model: {model}")
            res = requests.post(url, json=payload, timeout=60)
            res.raise_for_status()
            
            result = res.json()
            logger.info(f"ollama response received: {len(result.get('response', ''))} chars")
            
            if 'response' not in result:
                logger.error(f"ollama response missing 'response' field: {result}")
                return {"response": "error: ollama didn't return a response"}
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error("ollama request timed out")
            raise Exception("ollama request timed out - model might be slow or not loaded")
        except requests.exceptions.ConnectionError:
            logger.error("can't connect to ollama - is it running?")
            raise Exception("can't connect to ollama - make sure it's running on localhost:11434")
        except Exception as e:
            logger.error(f"ollama request failed: {e}")
            raise

class DocumentProcessor:
    def extract_text_from_pdf(self, file_path: str) -> str:
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                txt = ""
                for pg in pdf_reader.pages:
                    txt += pg.extract_text() + "\n"
                return txt
        except Exception as e:
            logger.error(f"error extracting pdf text: {e}")
            return ""
    
    def segment_text(self, txt: str, segment_size: int = 500, overlap: int = 50) -> List[str]:
        txt = re.sub(r'\s+', ' ', txt.strip())

        sentences = txt.split('. ')
        segments = []
        current_segment = ""
        
        for sentence in sentences:
            if len(current_segment + sentence) < segment_size:
                current_segment += sentence + ". "
            else:
                if current_segment:
                    segments.append(current_segment.strip())
                current_segment = sentence + ". "
        
        if current_segment:
            segments.append(current_segment.strip())
            
        return segments

class VectorSearch:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = None
        self.segments = []
    
    def create_embeddings(self, segments: List[str]):
        self.segments = segments
        embeddings = self.model.encode(segments)
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        self.index.add(embeddings.astype('float32'))
    
    def search(self, query: str, top_k: int = 3) -> List[str]:
        if not self.index or not self.segments:
            return []
        
        query_embedding = self.model.encode([query])
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        
        scores, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
        relevant_txt = []
        for i, score in zip(indices[0], scores[0]):
            if score > 0.1:
                relevant_txt.append(self.segments[i])
        
        if not relevant_txt and len(indices[0]) > 0:
            relevant_txt.append(self.segments[indices[0][0]])
        
        return relevant_txt

class AIProcessor:
    def __init__(self, groq_api_key: str = None, ollama_url: str = "http://localhost:11434"):
        self.groq_client = Groq(api_key=groq_api_key) if groq_api_key else None
        self.ollama_client = OllamaClient(ollama_url)
        
        self.groq_available = bool(groq_api_key)
        self.ollama_available = self.check_ollama()
        
        logger.info(f"ai services - groq: {self.groq_available}, ollama: {self.ollama_available}")
    
    def check_ollama(self) -> bool:
        try:
            res = requests.get(f"{self.ollama_client.base_url}/api/tags", timeout=10)
            res.raise_for_status()
            
            models_data = res.json()
            models = models_data.get('models', [])
            
            logger.info(f"ollama check: found {len(models)} models")
            if models:
                logger.info(f"available models: {[m['name'] for m in models]}")
            
            return len(models) > 0
            
        except requests.exceptions.ConnectionError:
            logger.warning("ollama server not running or not accessible")
            return False
        except Exception as e:
            logger.error(f"error checking ollama: {e}")
            return False
    
    def get_available_services(self) -> List[str]:
        services = []
        if self.groq_available:
            services.append("groq")
        if self.ollama_available:
            services.append("ollama")
        return services
    
    def get_ollama_models(self) -> List[str]:
        try:
            res = requests.get(f"{self.ollama_client.base_url}/api/tags", timeout=5)
            models = res.json().get('models', [])
            return [model['name'] for model in models]
        except:
            return []
    
    def generate_answer(self, question: str, context: List[str], service: str = "groq", model: str = None) -> str:
        context_txt = "\n\n".join(context)
        prompt = f"""        
you are analyzing a document. based on the content below, answer user's question clearly and concisely.

document content:
{context_txt}

user question: {question}

instructions:
- answer based only on the provided content
- if the content doesn't contain the answer, say "i don't see information about that in this document"
- keep your answer concise but complete
- don't use markdown formatting in your response

answer:"""
        
        try:
            if service == "groq" and self.groq_available:
                res = self.groq_client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[
                        {"role": "system", "content": "you are a helpful assistant that answers questions based on provided document content. be concise and accurate."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1
                )
                return res.choices[0].message.content
            
            elif service == "ollama" and self.ollama_available:
                if not model:
                    models = self.get_ollama_models()
                    model = models[0] if models else "llama3.2"
                
                res = self.ollama_client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": "you are a helpful assistant that answers questions based on provided document content. be concise and accurate."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1
                )
                return res.get('response', 'no response from ollama')
            
            else:
                return f"service '{service}' is not available"
                
        except Exception as e:
            logger.error(f"error generating ai response with {service}: {e}")
            return f"|X| sorry, i encountered an error while processing your question with {service} |X|"

class DocumentBot:
    def __init__(self, telegram_token: str, groq_api_key: str = None):
        self.bot = telebot.TeleBot(telegram_token)
        self.docProcessor = DocumentProcessor()
        self.aiProcessor = AIProcessor(groq_api_key)
        
        self.userSessions: Dict[int, VectorSearch] = {}
        self.userPrefs: Dict[int, Dict] = {}
        
        self.setup_handlers()
    
    def get_user_ai_service(self, user_id: int) -> str:
        return self.userPrefs.get(user_id, {}).get('ai_service', 'groq')
    
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start', 'help'])
        def handle_start(message):
            welcome_txt = """
Welcome to AI Document Bot!

I can help You analyze PDF documents and answer questions about their content.

How to use me:
1. Choose your AI service with /settings
2. Send me a PDF file (max 20MB - telegram limit)
3. Wait for processing confirmation
4. Ask questions about the document

Commands:
/start - show this message
/settings - choose AI service (Groq/Ollama)
/models - list and switch ollama models
/status - check ai services status
/clear - clear current document
/help - show help

Let's get started! Use /settings to choose your AI, then send me a PDF file!
"""
            self.bot.send_message(message.chat.id, welcome_txt)
        
        @self.bot.message_handler(commands=['settings'])
        def handle_settings(message):
            self.show_ai_settings(message)
        
        @self.bot.message_handler(commands=['models'])
        def handle_models(message):
            self.show_ollama_models_command(message)
        
        @self.bot.message_handler(commands=['status'])
        def handle_status(message):
            self.show_status(message)
        
        @self.bot.message_handler(commands=['clear'])
        def handle_clear(message):
            userId = message.from_user.id
            if userId in self.userSessions:
                del self.userSessions[userId]
            self.bot.send_message(message.chat.id, "|OK| Document Cleared. Send a new PDF to start over.")
        
        @self.bot.message_handler(content_types=['document'])
        def handle_document(message):
            self.process_document(message)
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_question(message):
            self.answer_question(message)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self.handle_callback_query(call)
    
    def show_ai_settings(self, message):
        available_services = self.aiProcessor.get_available_services()
        
        if not available_services:
            self.bot.send_message(message.chat.id, "|X| No AI services are available. Check your Groq API key or Ollama installation.")
            return
        
        markup = types.InlineKeyboardMarkup()
        
        for service in available_services:
            status = "ACTIVE" if service == self.get_user_ai_service(message.from_user.id) else ""
            if service == "groq":
                markup.add(types.InlineKeyboardButton(f"{status} Groq (Cloud/Fast)", callback_data=f"ai_service_groq"))
            elif service == "ollama":
                markup.add(types.InlineKeyboardButton(f"{status} Ollama (Local/Private)", callback_data=f"ai_service_ollama"))
        
        if "ollama" in available_services:
            models = self.aiProcessor.get_ollama_models()
            if models:
                markup.add(types.InlineKeyboardButton("Choose Ollama Model", callback_data="show_ollama_models"))
        
        current_service = self.get_user_ai_service(message.from_user.id)
        settings_txt = f"""AI Service Settings

Current: {current_service.upper()}

Available services:
• Groq: Fast cloud AI (requires API key)
• Ollama: Local AI models (private, slower)

Choose your preferred service:"""
        
        self.bot.send_message(message.chat.id, settings_txt, reply_markup=markup)
    
    def handle_callback_query(self, call):
        user_id = call.from_user.id
        data = call.data
        
        if data.startswith("ai_service_"):
            service = data.replace("ai_service_", "")
            
            if user_id not in self.userPrefs:
                self.userPrefs[user_id] = {}
            self.userPrefs[user_id]['ai_service'] = service
            
            self.bot.answer_callback_query(call.id, f"AI service set to {service.upper()}")
            self.bot.edit_message_text(f"AI service changed to {service.upper()}\n\nYou can now upload a PDF document!", 
                                     call.message.chat.id, call.message.message_id)
        
        elif data == "show_ollama_models":
            models = self.aiProcessor.get_ollama_models()
            markup = types.InlineKeyboardMarkup()
            
            for model in models[:10]:
                markup.add(types.InlineKeyboardButton(model, callback_data=f"ollama_model_{model}"))
            markup.add(types.InlineKeyboardButton("Back", callback_data="back_to_settings"))
            
            self.bot.edit_message_text("Available Ollama Models:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
        elif data.startswith("ollama_model_"):
            model = data.replace("ollama_model_", "")
            
            if user_id not in self.userPrefs:
                self.userPrefs[user_id] = {}
            self.userPrefs[user_id]['ollama_model'] = model
            
            self.bot.answer_callback_query(call.id, f"Ollama model set to {model}")
            self.bot.edit_message_text(f"Ollama model changed to {model}\n\nYou can now upload a PDF document!", 
                                     call.message.chat.id, call.message.message_id)
        
        elif data.startswith("select_model_"):
            model = data.replace("select_model_", "")
            
            if user_id not in self.userPrefs:
                self.userPrefs[user_id] = {}
            self.userPrefs[user_id]['ollama_model'] = model
            self.userPrefs[user_id]['ai_service'] = 'ollama'
            
            self.bot.answer_callback_query(call.id, f"Switched to Ollama with {model}")
            self.bot.edit_message_text(f"Ollama model changed to: {model}\n\nYou can now upload a PDF document!", 
                                     call.message.chat.id, call.message.message_id)
            self.show_ai_settings_edit(call.message)
    
    def show_ollama_models_command(self, message):
        if not self.aiProcessor.ollama_available:
            self.bot.send_message(message.chat.id, "|X| Ollama is not available. Make sure it's running with models installed.")
            return
        
        models = self.aiProcessor.get_ollama_models()
        if not models:
            self.bot.send_message(message.chat.id, "|X| No Ollama models found. Install models with: ollama pull llama3.2")
            return
        
        current_model = self.userPrefs.get(message.from_user.id, {}).get('ollama_model', models[0])
        
        markup = types.InlineKeyboardMarkup()
        for model in models:
            status = "ACTIVE" if model == current_model else ""
            markup.add(types.InlineKeyboardButton(f"{status} {model}", callback_data=f"select_model_{model}"))
        
        models_txt = f"""Ollama Models

Current model: {current_model}

Available models:"""
        
        self.bot.send_message(message.chat.id, models_txt, reply_markup=markup)
    
    def show_status(self, message):
        status_txt = "AI Services Status\n\n"
        
        if self.aiProcessor.groq_available:
            status_txt += "GROQ: Available\n"
        else:
            status_txt += "GROQ: Not available (no API key)\n"
        
        if self.aiProcessor.ollama_available:
            models = self.aiProcessor.get_ollama_models()
            status_txt += f"OLLAMA: Available ({len(models)} models)\n"
            if models:
                status_txt += f"   Models: {', '.join(models[:3])}"
                if len(models) > 3:
                    status_txt += f" and {len(models)-3} more"
                status_txt += "\n"
        else:
            status_txt += "OLLAMA: Not available (not running or no models)\n"
        
        user_id = message.from_user.id
        current_service = self.get_user_ai_service(user_id)
        status_txt += f"\nYour current AI: {current_service.upper()}"
        
        if current_service == "ollama":
            current_model = self.userPrefs.get(user_id, {}).get('ollama_model', 'default')
            status_txt += f"\nYour current model: {current_model}"
        
        if user_id in self.userSessions:
            status_txt += "\nDocument: Loaded and ready for questions"
        else:
            status_txt += "\nDocument: No document loaded"
        
        self.bot.send_message(message.chat.id, status_txt)
    
    def show_ai_settings_edit(self, message):
        available_services = self.aiProcessor.get_available_services()
        markup = types.InlineKeyboardMarkup()
        
        for service in available_services:
            status = "ACTIVE" if service == self.get_user_ai_service(message.chat.id) else ""
            if service == "groq":
                markup.add(types.InlineKeyboardButton(f"{status} Groq (Cloud/Fast)", callback_data=f"ai_service_groq"))
            elif service == "ollama":
                markup.add(types.InlineKeyboardButton(f"{status} Ollama (Local/Private)", callback_data=f"ai_service_ollama"))
        
        current_service = self.get_user_ai_service(message.chat.id)
        settings_txt = f"""AI Service Settings

Current: {current_service.upper()}

Choose your preferred service:"""
        
        self.bot.edit_message_text(settings_txt, message.chat.id, message.message_id, reply_markup=markup)
    
    def process_document(self, message):
        userId = message.from_user.id
        
        if not message.document.file_name.lower().endswith('.pdf'):
            self.bot.send_message(message.chat.id, "|X| Please Send a PDF file only.")
            return
        
        if message.document.file_size > 20*1024*1024:
            self.bot.send_message(message.chat.id, "|X| File is too large. Telegram limits bot uploads to 20MB.")
            return
        
        available_services = self.aiProcessor.get_available_services()
        if not available_services:
            self.bot.send_message(message.chat.id, "|X| No AI services available. Use /settings to configure.")
            return
        
        current_service = self.get_user_ai_service(userId)
        if current_service not in available_services:
            self.bot.send_message(message.chat.id, f"|X| {current_service.upper()} is not available. Use /settings to choose another service.")
            return
        
        processing_msg = self.bot.send_message(message.chat.id, f"Processing your PDF with {current_service.upper()}... this might take a moment.")
        
        try:
            file_info = self.bot.get_file(message.document.file_id)
            downloaded_file = self.bot.download_file(file_info.file_path)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(downloaded_file)
                temp_file_path = temp_file.name
            
            txt = self.docProcessor.extract_text_from_pdf(temp_file_path)
            
            os.unlink(temp_file_path)
            
            if not txt.strip():
                self.bot.edit_message_text("|X| couldn't extract text from this pdf. the file might be image-based or corrupted.", 
                                         message.chat.id, processing_msg.message_id)
                return
            
            segments = self.docProcessor.segment_text(txt)
            
            if not segments:
                self.bot.edit_message_text("|X| the document appears to be empty or unreadable.", 
                                         message.chat.id, processing_msg.message_id)
                return
            
            vector_search = VectorSearch()
            vector_search.create_embeddings(segments)
            
            self.userSessions[userId] = vector_search
            
            success_txt = f"""
|DONE| Document Processed Successfully!

AI Service: {current_service.upper()}
Extracted {len(segments)} text segments
Document: {message.document.file_name}

Now you can ask questions about the document!
Examples: "what is the main topic?" or "summarize the key points"
"""
            self.bot.edit_message_text(success_txt, message.chat.id, processing_msg.message_id)
            
        except Exception as e:
            logger.error(f"error processing document: {e}")
            self.bot.edit_message_text("error processing document. please try again with a different file.", 
                                     message.chat.id, processing_msg.message_id)
    
    def answer_question(self, message):
        userId = message.from_user.id
        
        if userId not in self.userSessions:
            self.bot.send_message(message.chat.id, "Please upload a PDF document first!")
            return
        
        question = message.text.strip()
        if not question:
            self.bot.send_message(message.chat.id, "Please ask a question about your document.")
            return
        
        ai_service = self.get_user_ai_service(userId)
        ollama_model = self.userPrefs.get(userId, {}).get('ollama_model', None)
        
        self.bot.send_chat_action(message.chat.id, 'typing')
        
        try:
            vector_search = self.userSessions[userId]
            relevant_txt = vector_search.search(question, top_k=3)
            
            if not relevant_txt:
                self.bot.send_message(message.chat.id, "I couldn't find relevant information in the document to answer your question.")
                return
            
            answer = self.aiProcessor.generate_answer(question, relevant_txt, service=ai_service, model=ollama_model)
            
            safe_answer = answer.replace('*', '').replace('_', '').replace('[', '').replace(']', '')
            safe_res = f"Question: {question}\n\nAnswer ({ai_service.upper()}):\n{safe_answer}"
            
            self.bot.send_message(message.chat.id, safe_res)
            
        except Exception as e:
            logger.error(f"error answering question: {e}")
            self.bot.send_message(message.chat.id, "Error processing your question. Please try again.")
    
    def run(self):
        logger.info("ai document bot started!")
        logger.info(f"available ai services: {self.aiProcessor.get_available_services()}")
        self.bot.polling(none_stop=True)

def main():
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    
    if not TELEGRAM_BOT_TOKEN:
        print("---- |X| env var for TG BOT TOKEN is either NOT BEING READ or NOT SET ----")
        return
    
    if not GROQ_API_KEY:
        print("---- no groq api key found, only ollama will be available ----")
    
    bot = DocumentBot(TELEGRAM_BOT_TOKEN, GROQ_API_KEY)
    bot.run()

if __name__ == "__main__":
    main()
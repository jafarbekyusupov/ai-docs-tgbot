import tempfile
import os
import logging
from typing import Dict
from telebot import types

logger = logging.getLogger(__name__)

class BotHandlers:
    def __init__(self, bot, doc_procsr, ai_procsr, user_sess: Dict, user_prefs: Dict):
        self.bot = bot
        self.doc_procsr = doc_procsr
        self.ai_procsr = ai_procsr
        self.user_sess = user_sess
        self.user_prefs = user_prefs
    
    def get_user_ai_service(self, uid: int) -> str:
        return self.user_prefs.get(uid, {}).get('ai_service', 'groq')
    
    def handle_start(self, message):
        welcome_msg = """
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
        self.bot.send_message(message.chat.id, welcome_msg)
    
    def handle_settings(self, message):
        self.show_ai_settings(message)
    
    def handle_models(self, message):
        self.show_ollama_models_command(message)
    
    def handle_status(self, message):
        self.show_status(message)
    
    def handle_clear(self, message):
        uid = message.from_user.id
        if uid in self.user_sess:
            del self.user_sess[uid]
        self.bot.send_message(message.chat.id, "|OK| Document Cleared. Send a new PDF to start over.")
    
    def handle_document(self, message):
        self.process_document(message)
    
    def handle_question(self, message):
        self.answer_question(message)
    
    def handle_callback_query(self, call):
        uid = call.from_user.id
        data = call.data
        
        if data.startswith("ai_service_"):
            service = data.replace("ai_service_", "")
            
            if uid not in self.user_prefs:
                self.user_prefs[uid] = {}
            self.user_prefs[uid]['ai_service'] = service
            
            self.bot.answer_callback_query(call.id, f"AI service set to {service.upper()}")
            self.bot.edit_message_text(f"AI service changed to {service.upper()}\n\nYou can now upload a PDF document!", 
                                     call.message.chat.id, call.message.message_id)
        
        elif data == "show_ollama_models":
            models = self.ai_procsr.get_ollama_models()
            markup = types.InlineKeyboardMarkup()
            
            for model in models[:10]:
                markup.add(types.InlineKeyboardButton(model, callback_data=f"ollama_model_{model}"))
            markup.add(types.InlineKeyboardButton("Back", callback_data="back_to_settings"))
            
            self.bot.edit_message_text("Available Ollama Models:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
        elif data.startswith("ollama_model_"):
            model = data.replace("ollama_model_", "")
            
            if uid not in self.user_prefs:
                self.user_prefs[uid] = {}
            self.user_prefs[uid]['ollama_model'] = model
            
            self.bot.answer_callback_query(call.id, f"Ollama model set to {model}")
            self.bot.edit_message_text(f"Ollama model changed to {model}\n\nYou can now upload a PDF document!", 
                                     call.message.chat.id, call.message.message_id)
        
        elif data.startswith("select_model_"):
            model = data.replace("select_model_", "")
            
            if uid not in self.user_prefs:
                self.user_prefs[uid] = {}
            self.user_prefs[uid]['ollama_model'] = model
            self.user_prefs[uid]['ai_service'] = 'ollama'
            
            self.bot.answer_callback_query(call.id, f"Switched to Ollama with {model}")
            self.bot.edit_message_text(f"Ollama model changed to: {model}\n\nYou can now upload a PDF document!", 
                                     call.message.chat.id, call.message.message_id)
            self.show_ai_settings_edit(call.message)
    
    def show_ai_settings(self, message):
        avail_services = self.ai_procsr.get_available_services()
        
        if not avail_services:
            self.bot.send_message(message.chat.id, "|X| No AI services are available. Check your Groq API key or Ollama installation.")
            return
        
        markup = types.InlineKeyboardMarkup()
        
        for service in avail_services:
            status = "ACTIVE" if service == self.get_user_ai_service(message.from_user.id) else ""
            if service == "groq":
                markup.add(types.InlineKeyboardButton(f"{status} Groq (Cloud/Fast)", callback_data=f"ai_service_groq"))
            elif service == "ollama":
                markup.add(types.InlineKeyboardButton(f"{status} Ollama (Local/Private)", callback_data=f"ai_service_ollama"))
        
        if "ollama" in avail_services:
            models = self.ai_procsr.get_ollama_models()
            if models:
                markup.add(types.InlineKeyboardButton("Choose Ollama Model", callback_data="show_ollama_models"))
        
        curr_srvc = self.get_user_ai_service(message.from_user.id)
        settings_txt = f"""AI Service Settings

Current: {curr_srvc.upper()}

Available services:
• Groq: Fast cloud AI (requires API key)
• Ollama: Local AI models (private, slower)

Choose your preferred service:"""
        
        self.bot.send_message(message.chat.id, settings_txt, reply_markup=markup)
    
    def show_ollama_models_command(self, message):
        if not self.ai_procsr.ollama_isAvail:
            self.bot.send_message(message.chat.id, "|X| Ollama is not available. Make sure it's running with models installed.")
            return
        
        models = self.ai_procsr.get_ollama_models()
        if not models:
            self.bot.send_message(message.chat.id, "|X| No Ollama models found. Install models with: ollama pull llama3.2")
            return
        
        curr_model = self.user_prefs.get(message.from_user.id, {}).get('ollama_model', models[0])
        
        markup = types.InlineKeyboardMarkup()
        for model in models:
            status = "ACTIVE" if model == curr_model else ""
            markup.add(types.InlineKeyboardButton(f"{status} {model}", callback_data=f"select_model_{model}"))
        
        models_txt = f"""Ollama Models

Current model: {curr_model}

Available models:"""
        
        self.bot.send_message(message.chat.id, models_txt, reply_markup=markup)
    
    def show_status(self, message):
        status_msg = "AI Services Status\n\n"
        
        if self.ai_procsr.groq_isAvail:
            status_msg += "GROQ: Available\n"
        else:
            status_msg += "GROQ: Not available (no API key)\n"
        
        if self.ai_procsr.ollama_isAvail:
            models = self.ai_procsr.get_ollama_models()
            status_msg += f"OLLAMA: Available ({len(models)} models)\n"
            if models:
                status_msg += f"   Models: {', '.join(models[:3])}"
                if len(models) > 3:
                    status_msg += f" and {len(models)-3} more"
                status_msg += "\n"
        else:
            status_msg += "OLLAMA: Not available (not running or no models)\n"
        
        uid = message.from_user.id
        curr_srvc = self.get_user_ai_service(uid)
        status_msg += f"\nYour current AI: {curr_srvc.upper()}"
        
        if curr_srvc == "ollama":
            curr_model = self.user_prefs.get(uid, {}).get('ollama_model', 'default')
            status_msg += f"\nYour current model: {curr_model}"
        
        if uid in self.user_sess:
            status_msg += "\nDocument: Loaded and ready for questions"
        else:
            status_msg += "\nDocument: No document loaded"
        
        self.bot.send_message(message.chat.id, status_msg)
    
    def show_ai_settings_edit(self, message):
        avail_services = self.ai_procsr.get_available_services()
        markup = types.InlineKeyboardMarkup()
        
        for service in avail_services:
            status = "ACTIVE" if service == self.get_user_ai_service(message.chat.id) else ""
            if service == "groq":
                markup.add(types.InlineKeyboardButton(f"{status} Groq (Cloud/Fast)", callback_data=f"ai_service_groq"))
            elif service == "ollama":
                markup.add(types.InlineKeyboardButton(f"{status} Ollama (Local/Private)", callback_data=f"ai_service_ollama"))
        
        curr_srvc = self.get_user_ai_service(message.chat.id)
        settings_txt = f"""AI Service Settings

Current: {curr_srvc.upper()}

Choose your preferred service:"""
        
        self.bot.edit_message_text(settings_txt, message.chat.id, message.message_id, reply_markup=markup)
    
    def process_document(self, message):
        from vector_search import VectorSearch
        
        uid = message.from_user.id
        
        if not message.document.file_name.lower().endswith('.pdf'):
            self.bot.send_message(message.chat.id, "|X| Please Send a PDF file only.")
            return
        
        if message.document.file_size > 20*1024*1024:
            self.bot.send_message(message.chat.id, "|X| File is too large. Telegram limits bot uploads to 20MB.")
            return
        
        avail_services = self.ai_procsr.get_available_services()
        if not avail_services:
            self.bot.send_message(message.chat.id, "|X| No AI services available. Use /settings to configure.")
            return
        
        curr_srvc = self.get_user_ai_service(uid)
        if curr_srvc not in avail_services:
            self.bot.send_message(message.chat.id, f"|X| {curr_srvc.upper()} is not available. Use /settings to choose another service.")
            return
        
        procsng_msg = self.bot.send_message(message.chat.id, f"Processing your PDF with {curr_srvc.upper()}... this might take a moment.")
        
        try:
            file_info = self.bot.get_file(message.document.file_id)
            file = self.bot.download_file(file_info.file_path)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file)
                tmp_file_path = tmp_file.name
            
            txt = self.doc_procsr.extract_text_from_pdf(tmp_file_path)
            
            os.unlink(tmp_file_path)
            
            if not txt.strip():
                self.bot.edit_message_text("|X| Couldn't extract text from this pdf. The file might be image-based or corrupted.", 
                                         message.chat.id, procsng_msg.message_id)
                return
            
            segments = self.doc_procsr.segment_text(txt)
            
            if not segments:
                self.bot.edit_message_text("|X| The document appears to be empty or unreadable.", 
                                         message.chat.id, procsng_msg.message_id)
                return
            
            vector_search = VectorSearch()
            vector_search.create_embeddings(segments)
            
            self.user_sess[uid] = vector_search
            
            success_txt = f"""
|DONE| Document Processed Successfully!

AI Service: {curr_srvc.upper()}
Extracted {len(segments)} text segments
Document: {message.document.file_name}

Now you can ask questions about the document!
Examples: "What is the Main Topic?" or "Summarize the Key Points"
"""
            self.bot.edit_message_text(success_txt, message.chat.id, procsng_msg.message_id)
            
        except Exception as e:
            logger.error(f"error processing document: {e}")
            self.bot.edit_message_text("error processing document. please try again with a different file.", 
                                     message.chat.id, procsng_msg.message_id)
    
    def answer_question(self, message):
        uid = message.from_user.id
        
        if uid not in self.user_sess:
            self.bot.send_message(message.chat.id, "Please upload a PDF document first!")
            return
        
        question = message.text.strip()
        if not question:
            self.bot.send_message(message.chat.id, "Please ask a question about your document.")
            return
        
        ai_service = self.get_user_ai_service(uid)
        ollama_model = self.user_prefs.get(uid, {}).get('ollama_model', None)
        
        self.bot.send_chat_action(message.chat.id, 'typing')
        
        try:
            vector_search = self.user_sess[uid]
            relevnt_txt = vector_search.search(question, top_k=3)
            
            if not relevnt_txt:
                self.bot.send_message(message.chat.id, "I couldn't find relevant information in the document to answer your question.")
                return
            
            ans = self.ai_procsr.generate_answer(question, relevnt_txt, service=ai_service, model=ollama_model)
            
            safe_ans = ans.replace('*', '').replace('_', '').replace('[', '').replace(']', '')
            safe_res = f"Question: {question}\n\nAnswer ({ai_service.upper()}):\n{safe_ans}"
            
            self.bot.send_message(message.chat.id, safe_res)
            
        except Exception as e:
            logger.error(f"error answering question: {e}")
            self.bot.send_message(message.chat.id, "Error processing your question. Please try again.")

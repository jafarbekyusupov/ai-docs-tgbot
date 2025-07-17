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
1. Choose your AI service with /settings (GROQ is a default setting, but you may switch to Ollama model if you wish)
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
/debug <your question> - debug search results

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
    
    def handle_debug(self, message): # to see whats happening
        uid = message.from_user.id        
        if uid not in self.user_sess: self.bot.send_message(message.chat.id, "Please upload a PDF document first!"); return
        
        query = message.text.replace('/debug', '').strip() # extract query from msg | rm /debug cmd
        if not query: self.bot.send_message(message.chat.id, "Usage: /debug your search query here"); return
        
        vector_search = self.user_sess[uid]
        try:
            if hasattr(vector_search, 'debug_search'):
                debug_info = vector_search.debug_search(query)        
                debug_msg = f"Debug Search Results for: '{query}'\n\n"
                debug_msg += f"Total segments: {debug_info.get('total_segments', 'unknown')}\n\n"
                
                if 'search_strategies' in debug_info:
                    for strat,resz in debug_info['search_strategies'].items():
                        debug_msg += f"{strat.upper()}: {resz.get('found', 0)} i,  s\n"
                
                debug_msg += "\nTop matches:\n"
                if 'search_strategies' in debug_info:
                    for strat, resz in debug_info['search_strategies'].items():
                        if 'top_3' in resz:
                            for i,match in enumerate(resz['top_3'][:2]):  # show top 2
                                debug_msg += f"{i+1}. {strat} - Score: {match['score']:.3f}\n"
                                debug_msg += f"   {match['preview']}\n\n"
                                
                if len(debug_msg)>4000: 
                    debug_msg = debug_msg[:4000] + "...\n\n[Message truncated]" # split long msgs
                
                self.bot.send_message(message.chat.id, debug_msg)
            else: # if fail → simple search
                resz = vector_search.search(query, top_k=8)
                debug_msg = f"Simple Debug for: '{query}'\n\nFound {len(resz)} segments:\n\n"
                for i,res in enumerate(resz[:5]):
                    preview = res[:150] + "..." if len(res) > 150 else res
                    debug_msg += f"{i+1}. {preview}\n\n"
                
                self.bot.send_message(message.chat.id, debug_msg)
                
        except Exception as e:
            logger.error(f"debug search error: {e}")
            self.bot.send_message(message.chat.id, f"Debug error: {str(e)}")
    
    def handle_document(self, message): self.process_document(message)
    def handle_question(self, message): self.answer_question(message)
    
    def handle_callback_query(self, call):
        uid = call.from_user.id
        data = call.data
        
        if data.startswith("ai_service_"):
            service = data.replace("ai_service_", "")
            
            if uid not in self.user_prefs: self.user_prefs[uid] = {}
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
            
            if uid not in self.user_prefs: self.user_prefs[uid] = {}
            self.user_prefs[uid]['ollama_model'] = model
            
            self.bot.answer_callback_query(call.id, f"Ollama model set to {model}")
            self.bot.edit_message_text(f"Ollama model changed to {model}\n\nYou can now upload a PDF document!", 
                                     call.message.chat.id, call.message.message_id)
        
        elif data.startswith("select_model_"):
            model = data.replace("select_model_", "")
            
            if uid not in self.user_prefs: self.user_prefs[uid] = {}
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
        for srvc in avail_services:
            status = "ACTIVE" if srvc == self.get_user_ai_service(message.from_user.id) else ""
            if srvc == "groq": markup.add(types.InlineKeyboardButton(f"{status} Groq (Cloud/Fast)", callback_data=f"ai_service_groq"))
            elif srvc == "ollama": markup.add(types.InlineKeyboardButton(f"{status} Ollama (Local/Private/Free)",callback_data=f"ai_service_ollama"))
        
        if "ollama" in avail_services:
            models = self.ai_procsr.get_ollama_models()
            if models: markup.add(types.InlineKeyboardButton("Choose Ollama Model", callback_data="show_ollama_models"))
        
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
            self.bot.send_message(message.chat.id, "|X| Ollama is NOT available. Make sure it's running with models installed.")
            return
        
        models = self.ai_procsr.get_ollama_models()
        if not models:
            self.bot.send_message(message.chat.id, "|X| No Ollama models found. Install models with: `ollama pull llama3.2`")
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
        
        if self.ai_procsr.groq_isAvail: status_msg += "GROQ: Available\n"
        else: status_msg += "GROQ: Not available (no API key)\n"
        
        if self.ai_procsr.ollama_isAvail:
            models = self.ai_procsr.get_ollama_models()
            status_msg += f"OLLAMA: Available ({len(models)} models)\n"
            if models:
                status_msg += f"   Models: {', '.join(models[:3])}"
                if len(models)>3: status_msg += f" and {len(models)-3} more"
                status_msg += "\n"
        else: status_msg += "OLLAMA: Not available (not running or no models)\n"
        
        uid = message.from_user.id
        curr_srvc = self.get_user_ai_service(uid)
        status_msg += f"\nYour current AI: {curr_srvc.upper()}"
        
        if curr_srvc == "ollama":
            curr_model = self.user_prefs.get(uid, {}).get('ollama_model', 'default')
            status_msg += f"\nYour current model: {curr_model}"
        
        if uid in self.user_sess: status_msg += "\nDocument: Loaded and ready for questions"
        else: status_msg += "\nDocument: No document loaded"
        
        self.bot.send_message(message.chat.id, status_msg)
    
    def show_ai_settings_edit(self, message):
        avail_services = self.ai_procsr.get_available_services()
        markup = types.InlineKeyboardMarkup()
        
        for srvc in avail_services:
            status = "ACTIVE" if srvc == self.get_user_ai_service(message.chat.id) else ""
            if srvc == "groq":
                markup.add(types.InlineKeyboardButton(f"{status} Groq (Cloud/Fast)", callback_data=f"ai_service_groq"))
            elif srvc == "ollama":
                markup.add(types.InlineKeyboardButton(f"{status} Ollama (Local/Private)", callback_data=f"ai_service_ollama"))
        
        curr_srvc = self.get_user_ai_service(message.chat.id)
        settings_txt = f"""AI Service Settings

Current: {curr_srvc.upper()}

Choose your preferred service:"""
        
        self.bot.edit_message_text(settings_txt, message.chat.id, message.message_id, reply_markup=markup)
    
    def process_document(self, message):
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
        
        processing_msg = self.bot.send_message(message.chat.id, f"Processing your PDF with {curr_srvc.upper()}... this might take a moment.")
        
        try:
            file_info = self.bot.get_file(message.document.file_id)
            file = self.bot.download_file(file_info.file_path)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file)
                tmp_file_path = tmp_file.name
            
            txt = self.doc_procsr.extract_text_from_pdf(tmp_file_path)
            os.unlink(tmp_file_path)
            
            if not txt.strip():
                self.bot.edit_message_text("|X| Couldn't extract text from this pdf. The file might be image-based or corrupted.", message.chat.id, processing_msg.message_id)
                return
            
            segmentation_type = "unknown"
            try: # try universal / mixed , if fials → simple
                segments = self.doc_procsr.segment_text(txt)
                segmentation_type = "universal"
                
                try:
                    from vector_search import VectorSearch
                    vector_search = VectorSearch()
                    vector_search.create_embeddings(segments)
                    search_type = "universal"
                except ImportError:
                    from vector_search import VectorSearch
                    vector_search = VectorSearch()
                    smp_sgmts = [seg["text"] if isinstance(seg, dict) else seg for seg in segments] # convert sgmts to simple strs for compat-ty
                    vector_search.create_embeddings_simple(smp_sgmts)
                    search_type = "basic"
                
            except Exception as e:
                logger.warning(f"universal segmentation failed, using simple: {e}")
                segments = self.doc_procsr.segment_text_simple(txt)
                segmentation_type = "simple"
                
                try: #basic vector search
                    from vector_search import VectorSearch
                    vector_search = VectorSearch()
                    vector_search.create_embeddings_simple(segments)
                    search_type = "basic"
                except:
                    logger.error("all vector search methods failed")
                    self.bot.edit_message_text("|X| Error setting up document search.", message.chat.id, processing_msg.message_id)
                    return
            
            if not segments:
                self.bot.edit_message_text("|X| The document appears to be empty or unreadable.",message.chat.id, processing_msg.message_id)
                return
            
            self.user_sess[uid] = vector_search
            success_txt = f"""
|DONE| Document Processed Successfully!

AI Service: {curr_srvc.upper()}
Extracted {len(segments)} text segments ({segmentation_type})
Search: {search_type}
Document: {message.document.file_name}

Now you can ask questions about the document!
Examples: "What is the Main Topic?" or "Summarize the Key Points"

Commands:
- Ask any question about the document
- /debug <query> - see detailed search results
"""
            self.bot.edit_message_text(success_txt, message.chat.id, processing_msg.message_id)
            
        except Exception as e:
            logger.error(f"error processing document: {e}")
            self.bot.edit_message_text(f"Error processing document: {str(e)}", message.chat.id, processing_msg.message_id)
    
    def answer_question(self, message):
        uid = message.from_user.id
        
        if uid not in self.user_sess: self.bot.send_message(message.chat.id, "Please upload a PDF document first!"); return
        
        question = message.text.strip()
        if not question: self.bot.send_message(message.chat.id, "Please ask a question about your document."); return
        
        ai_service = self.get_user_ai_service(uid)
        ollama_model = self.user_prefs.get(uid, {}).get('ollama_model', None)
        
        # safer typing indicator
        try: self.bot.send_chat_action(message.chat.id, 'typing')
        except: pass  # ignore if typing action fails
        
        if ai_service == "ollama":
            processing_msg = self.bot.send_message(message.chat.id, 
                                                   f"Processing with {ai_service.upper()}... this may take a moment (up to 1 minute)")
        
        try:
            vector_search = self.user_sess[uid]
            relevnt_txt = vector_search.search(question, top_k=5)
            
            if not relevnt_txt:
                msg = "I couldn't find relevant information in the document to answer your question."
                if ai_service == "ollama": self.bot.edit_message_text(msg, message.chat.id, processing_msg.message_id)
                else: self.bot.send_message(message.chat.id, msg)
                return
            
            ans = self.ai_procsr.generate_answer(question, relevnt_txt, service=ai_service, model=ollama_model)
            safe_ans = ans.replace('*', '').replace('_', '').replace('[', '').replace(']', '')
            safe_res = f"Question: {question}\n\nAnswer ({ai_service.upper()}):\n{safe_ans}"
            
            if ai_service == "ollama": self.bot.edit_message_text(safe_res, message.chat.id, processing_msg.message_id)
            else: self.bot.send_message(message.chat.id, safe_res)
            
        except Exception as e:
            logger.error(f"error answering question: {e}")
            error_msg = f"Error processing your question with {ai_service.upper()}: {str(e)}"
            if ai_service == "ollama" and 'processing_msg' in locals():
                try: self.bot.edit_message_text(error_msg, message.chat.id, processing_msg.message_id)
                except: self.bot.send_message(message.chat.id, error_msg)
            else: self.bot.send_message(message.chat.id, error_msg)
import requests
import logging
from typing import List
from groq import Groq
from ollama import OllamaClient

logger = logging.getLogger(__name__)

class AIProcessor:
    def __init__(self, groq_api_key: str = None, ollama_url: str = "http://localhost:11434"):
        self.groq_client = Groq(api_key=groq_api_key) if groq_api_key else None
        self.ollama_client = OllamaClient(ollama_url)
        
        self.groq_isAvail = bool(groq_api_key)
        self.ollama_isAvail = self.check_ollama()
        
        logger.info(f"ai services - groq: {self.groq_isAvail}, ollama: {self.ollama_isAvail}")
    
    def check_ollama(self) -> bool:
        try:
            greq = requests.get(f"{self.ollama_client.base_url}/api/tags", timeout=5)
            greq.raise_for_status()
            
            models_data = greq.json()
            models = models_data.get('models', [])
            
            logger.info(f"ollama check: found {len(models)} models")
            if models:
                logger.info(f"available models: {[m['name'] for m in models]}")
            
            return len(models)>0
            
        except requests.exceptions.ConnectionError:
            logger.warning("ollama not available - using groq only")
            return False
        except Exception as e:
            logger.error(f"error checking ollama: {e}")
            return False
        
    def get_available_services(self) -> List[str]:
        services = []
        if self.groq_isAvail:
            services.append("groq")
        if self.ollama_isAvail:
            services.append("ollama")
        return services
    
    def get_ollama_models(self) -> List[str]:
        try:
            greq = requests.get(f"{self.ollama_client.base_url}/api/tags", timeout=5)
            models = greq.json().get('models', [])
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
- do NOT use markdown formatting in your response

answer:"""
        
        try:
            if service == "groq" and self.groq_isAvail:
                groq_req = self.groq_client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[
                        {"role": "system", "content": "you are a helpful assistant that answers questions based on provided document content. be concise and accurate."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1
                )
                return groq_req.choices[0].message.content
            
            elif service == "ollama" and self.ollama_isAvail:
                if not model:
                    models = self.get_ollama_models()
                    model = models[0] if models else "llama3.2"
                
                lama_req = self.ollama_client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": "you are a helpful assistant that answers questions based on provided document content. be concise and accurate."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1
                )
                return lama_req.get('response', 'no response from ollama')
            
            else:
                return f"service '{service}' is not available"
                
        except Exception as e:
            logger.error(f"error generating ai response with {service}: {e}")
            return f"|X| sorry, i encountered an error while processing your question with {service} |X|"

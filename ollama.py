import requests
import logging
from typing import Dict, List

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
            preq = requests.post(url, json=payload, timeout=60)
            preq.raise_for_status()
            
            res = preq.json()
            logger.info(f"ollama response received: {len(res.get('response', ''))} chars")
            
            if 'response' not in res:
                logger.error(f"ollama response missing 'response' field: {res}")
                return {"response": "error: ollama didn't return a response"}
            
            return res
            
        except requests.exceptions.Timeout:
            logger.error("ollama req timed out")
            raise Exception("ollama reqeust timed out - model might be SLOW (most likely lol) or not loaded")
        except requests.exceptions.ConnectionError:
            logger.error("cant connect to ollama - is it running ?????????????????????")
            raise Exception("cant connect to ollama - check 11434 n make sure its nothing else on there except lama boyyyyy")
        except Exception as e:
            logger.error(f"ollama request failed: {e}")
            raise
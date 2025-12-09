import os
import requests
from .base import AIStrategy
from utils.bot_proxy import APIKeyMissingError, AIServiceError
from .prompts import SUMMARY_PROMPT_TEMPLATE

class DeepSeekStrategy(AIStrategy):
    def generate_summary(self, text_content: str) -> str:
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            raise APIKeyMissingError("DEEPSEEK_API_KEY no encontrada")
            
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = SUMMARY_PROMPT_TEMPLATE.format(text_content=text_content)
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                raise AIServiceError(f"Error DeepSeek API: {response.text}")
        except Exception as e:
             if isinstance(e, AIServiceError):
                 raise
             raise AIServiceError(f"Error conectando con DeepSeek: {str(e)}")

import os
import requests
from .base import AIStrategy
from utils.bot_proxy import APIKeyMissingError
from .prompts import SUMMARY_PROMPT_TEMPLATE

class GroqStrategy(AIStrategy):
    def generate_summary(self, text_content: str) -> str:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise APIKeyMissingError("GROQ_API_KEY no encontrada")
            
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = SUMMARY_PROMPT_TEMPLATE.format(text_content=text_content)
        
        data = {
            "model": "llama-3.3-70b-versatile", 
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            raise Exception(f"Error Groq API: {response.text}")

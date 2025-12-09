import os
import google.generativeai as genai
from .base import AIStrategy
from utils.bot_proxy import APIKeyMissingError
from .prompts import SUMMARY_PROMPT_TEMPLATE

class GeminiStrategy(AIStrategy):
    def generate_summary(self, text_content: str) -> str:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise APIKeyMissingError("GEMINI_API_KEY no encontrada")
            
        genai.configure(api_key=api_key)
        # Usando el modelo especificado anteriormente
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = SUMMARY_PROMPT_TEMPLATE.format(text_content=text_content)
        
        response = model.generate_content(prompt)
        return response.text

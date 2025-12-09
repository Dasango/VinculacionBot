import os
from .gemini_strategy import GeminiStrategy
from .deepseek_strategy import DeepSeekStrategy
from .groq_strategy import GroqStrategy
from .base import AIStrategy

class AIContext:
    def __init__(self):
        self._strategy: AIStrategy = None

    def set_strategy(self, strategy: AIStrategy):
        self._strategy = strategy

    def get_strategy(self) -> AIStrategy:
        provider = os.getenv('AI_PROVIDER', 'gemini').lower()
        
        if provider == 'deepseek':
            return DeepSeekStrategy()
        elif provider == 'groq':
            return GroqStrategy()
        else:
            return GeminiStrategy()

    def generate_summary(self, text_content: str) -> str:
        strategy = self.get_strategy()
        return strategy.generate_summary(text_content)

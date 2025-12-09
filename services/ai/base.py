from abc import ABC, abstractmethod

class AIStrategy(ABC):
    @abstractmethod
    def generate_summary(self, text_content: str) -> str:
        pass

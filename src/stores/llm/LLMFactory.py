from src.stores.llm.providers.AISuiteProvider import AISuiteProvider
from src.helpers.config import get_settings

class LLMFactory:
    @staticmethod
    def get_llm_provider(model_name: str = None):
        settings = get_settings()
        selected_model = model_name or settings.MODEL
        
        
        return AISuiteProvider(model_name=selected_model)
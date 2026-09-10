import os
from pathlib import Path
import aisuite as ai
from dotenv import load_dotenv
from src.stores.llm.LLMInterface import LLMInterface


SRC_DIR = Path(__file__).resolve().parents[3]
env_path = SRC_DIR / ".env"


load_dotenv(dotenv_path=env_path)

class AISuiteProvider(LLMInterface):
    def __init__(self, model_name: str, client=None):
        self.model_name = model_name
        
        
        cohere_key = os.getenv("CO_API_KEY") or os.getenv("COHERE_API_KEY")
        
        if cohere_key:
            os.environ["CO_API_KEY"] = cohere_key.strip().strip("'\"")
            os.environ["COHERE_API_KEY"] = cohere_key.strip().strip("'\"")

        self.client = client or ai.Client()
        self.tools = None

    def bind_tools(self, tools: list):
        self.tools = tools
        return self

    def generate(self, prompt: str, system_instruction: str = "", use_tools: bool = True) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.0,
        }
        
        
        if use_tools and self.tools:
            kwargs["tools"] = self.tools

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
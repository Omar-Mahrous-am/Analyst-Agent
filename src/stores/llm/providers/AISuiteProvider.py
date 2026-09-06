import aisuite as ai
from src.stores.llm.LLMInterface import LLMInterface

class AISuiteProvider(LLMInterface):
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.client = ai.Client()

    def generate(self, prompt: str, system_instruction: str = "") -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.0
        )
        return response.choices[0].message.content
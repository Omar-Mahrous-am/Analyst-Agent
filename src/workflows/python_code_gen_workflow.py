from src.stores.llm.templates.locales.en.en_prompts import advanced_analysis_plan_prompt
import re


class PythonCodeGenWorkflow:
    """Handles Python code generation and advanced analysis workflow."""
    
    def __init__(self, client , system_prompt):
        """
        Args:
            client: AISuiteProvider instance for LLM calls
        """
        self.client = client
         
        self.system_prompt = system_prompt

    def plan_advanced_analysis(self, state: dict) -> dict:
        """Generate Python code for advanced analysis and visualization."""
        prompt=advanced_analysis_plan_prompt.format(
            user_request=state['question'],
            schema_block=state['schema'],
            sql_query=state['sql_v2'],
            df=state['df_v2']
        )
        response = self.client.generate(prompt=prompt, system_instruction=self.system_prompt)

        if not response.text:
            raise RuntimeError("Empty content passed to code executor.")    
        m = re.search(r"<execute_python>(.*?)</execute_python>", response.text, re.DOTALL | re.IGNORECASE)
        return {"analysis_plan_code":m.group(1).strip() if m else response.text.strip()}

    def excution(self, state: dict) -> dict:
        """Execute Python code for advanced analysis and visualization."""
        # Implementation goes here
        pass

    def finalize_and_recommendation(self, state: dict) -> dict:
        """Finalize analysis and provide recommendations."""
        # Implementation goes here
        pass


    def reflect_and_check_analysis(self, state: dict) -> dict:
        """Reflect on analysis and check for errors."""
        # Implementation goes here
        pass


    def output_pdf(self, state: dict) -> dict:
        """Output the final analysis as a PDF."""
        # Implementation goes here
        pass


    
from langchain_core.messages import AIMessage
from tavily import TavilyClient


class WebSearchWorkflow:
    """Handles web search and LLM synthesis workflow."""
    
    def __init__(self, client, search_client: TavilyClient):
        """
        Args:
            client: AISuiteProvider instance for LLM calls
            search_client: TavilyClient instance for web search
        """
        self.client = client
        self.search_client = search_client

    def search_web(self, state: dict) -> dict:
        """Perform a web search using Tavily and synthesize an answer using the LLM."""
        query = state["question"]
    
        # 1. Perform deep web search using Tavily
        try:
            search_response = self.search_client.search(query, search_depth="advanced", max_results=3)
            results = search_response.get("results", [])
        except Exception:
            results = []

        # 2. Aggregate search context texts
        if not results:
            raw_search_data = "No search results found."
        else:
            raw_search_data = "\n\n".join([res.get("content", "") for res in results])

        # 3. Format standalone system prompt for web search
        web_system_prompt = (
            "You are a helpful general-knowledge AI assistant. "
            "Answer the user's question directly using the provided web search context. "
            "If the context contains the answer, explain it clearly."
        )

        prompt = f"User Question: {query}\n\nWeb Search Context:\n{raw_search_data}"
        
        final_answer = self.client.generate(prompt=prompt, system_instruction=web_system_prompt).strip()   

        return {"messages": [AIMessage(content=final_answer)], "result": final_answer}
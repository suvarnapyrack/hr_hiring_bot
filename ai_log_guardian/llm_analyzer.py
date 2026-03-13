import os
import requests
import json
import logging

logger = logging.getLogger("LLMAnalyzer")

class LLMAnalyzer:
    def __init__(self):
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.model = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-001")
        self.fallback_model = os.getenv("FALLBACK_MODEL", "llama3")

    def analyze_log(self, container_name, log_content):
        """
        Analyzes a log line using OpenRouter with Ollama fallback.
        """
        prompt = f"""
        Analyze the following error log from the container '{container_name}':
        
        LOG: {log_content}
        
        Provide the following in JSON format:
        1. severity: (LOW, MEDIUM, HIGH, CRITICAL)
        2. root_cause: Brief explanation of why this happened.
        3. suggested_fix: Steps to resolve the issue.
        4. is_actionable: Boolean.
        """

        try:
            if self.openrouter_api_key:
                return self._query_openrouter(prompt)
            else:
                logger.info("OpenRouter API key missing, falling back to Ollama.")
                return self._query_ollama(prompt)
        except Exception as e:
            logger.error(f"Error during LLM analysis: {e}")
            return self._query_ollama(prompt)

    def _query_openrouter(self, prompt):
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        response = requests.post(self.openrouter_url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

    def _query_ollama(self, prompt):
        logger.info(f"Using Ollama fallback with model: {self.fallback_model}")
        data = {
            "model": self.fallback_model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        response = requests.post(self.ollama_url, data=json.dumps(data))
        response.raise_for_status()
        return response.json().get('response', '{}')

if __name__ == "__main__":
    # Test logic
    analyzer = LLMAnalyzer()
    res = analyzer.analyze_log("test-container", "ERROR: Could not connect to database at 127.0.0.1:5432")
    print(res)

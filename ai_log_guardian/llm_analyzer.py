import os
import requests
import json
import logging

logger = logging.getLogger("LLMAnalyzer")

class LLMAnalyzer:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        self.fallback_model = os.getenv("FALLBACK_MODEL", "llama3")

    def analyze_log(self, container_name, log_content):
        """
        Analyzes a log line using Groq with Ollama fallback.
        """
        prompt = f"""
        Analyze this log line from the Docker container '{container_name}':
        
        LOG: {log_content}
        
        Respond ONLY in valid JSON with these fields:
        - severity: one of LOW, MEDIUM, HIGH, CRITICAL
        - root_cause: short explanation (1-2 sentences)
        - suggested_fix: concrete step(s) to resolve
        - is_actionable: true or false
        - is_noise: true if this is a routine/expected message, false if it needs attention
        """

        try:
            if self.groq_api_key:
                return self._query_groq(prompt)
            else:
                logger.info("Groq API key missing, falling back to Ollama.")
                return self._query_ollama(prompt)
        except Exception as e:
            logger.error(f"Error during LLM analysis: {e}")
            return self._query_ollama(prompt)

    def _query_groq(self, prompt):
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        response = requests.post(self.groq_url, headers=headers, data=json.dumps(data))
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

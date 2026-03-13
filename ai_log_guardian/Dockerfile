FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables (defaults)
ENV PYTHONUNBUFFERED=1

# Default: run in fully agentic LangGraph mode
# Override with --mode simple for legacy rule-based mode
CMD ["python", "main.py", "--mode", "agent"]

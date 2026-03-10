import os
import functools
import builtins
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Ensure prints are flushed immediately
builtins.print = functools.partial(print, flush=True)

# Load environment variables
load_dotenv(override=True)

# Initialize LLM — using Groq cloud API
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0
)

"""
LLM provider factory.
Switch provider by setting LLM_PROVIDER in your .env file:
  LLM_PROVIDER=anthropic  MODEL_NAME=claude-sonnet-4-6
  LLM_PROVIDER=openai     MODEL_NAME=gpt-4o
  LLM_PROVIDER=ollama     MODEL_NAME=llama3.2
"""

import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")
MODEL_NAME: str = os.getenv("MODEL_NAME", "claude-sonnet-4-6")


def get_llm():
    """Return a LangChain chat model based on LLM_PROVIDER env var."""
    if LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in your .env file.")
        return ChatAnthropic(model=MODEL_NAME, api_key=api_key, max_tokens=4096)

    elif LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in your .env file.")
        return ChatOpenAI(model=MODEL_NAME, api_key=api_key)

    elif LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(model=MODEL_NAME, base_url=base_url)

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. "
            "Valid options: anthropic, openai, ollama"
        )

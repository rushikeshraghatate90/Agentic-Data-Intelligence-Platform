
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()


def pick_llm(level: str):
    """
    Select a Groq LLM based on question complexity.

    Supported levels:
        low, medium, high, claude

    Returns:
        ChatGroq: Configured Groq chat model.
    """

    models = {
        "low": os.getenv("LLM_MODEL_LOW", "llama-3.1-8b-instant"),
        "medium": os.getenv("LLM_MODEL_MEDIUM", "llama-3.3-70b-versatile"),
        "high": os.getenv("LLM_MODEL_HIGH", "openai/gpt-oss-120b"),
        # Backward compatibility with the previous Claude option
        "claude": os.getenv("LLM_MODEL_HIGH", "openai/gpt-oss-120b"),
    }

    level = level.lower()

    if level not in models:
        raise ValueError(f"Unsupported level: {level}")

    return ChatGroq(
        model_name=models[level],
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    )


if __name__ == "__main__":
    llm_obj = pick_llm("low")
    response = llm_obj.invoke("What is the capital of France?")
    print(response.content)

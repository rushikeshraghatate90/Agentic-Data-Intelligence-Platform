
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq


# ==================================================
# ENVIRONMENT CONFIGURATION
# ==================================================

load_dotenv()


# ==================================================
# GROQ MODEL CONFIGURATION
# ==================================================

MODEL_CONFIG = {
    "low": "openai/gpt-oss-20b",
    "medium": "openai/gpt-oss-120b",
    "high": "openai/gpt-oss-120b",
    "claude": "openai/gpt-oss-120b",
}


# ==================================================
# LLM SELECTION
# ==================================================

def pick_llm(level: str) -> ChatGroq:
    """
    Select a Groq LLM based on question complexity.

    Supported levels:
        low
        medium
        high
        claude (legacy compatibility alias)

    Model selection:
        low    -> openai/gpt-oss-20b
        medium -> openai/gpt-oss-120b
        high   -> openai/gpt-oss-120b
        claude -> openai/gpt-oss-120b

    Returns:
        ChatGroq: Configured Groq chat model.
    """

    if not isinstance(level, str):
        raise TypeError("LLM level must be a string.")

    level = level.strip().lower()

    if level not in MODEL_CONFIG:
        raise ValueError(
            f"Unsupported LLM level: {level}. "
            f"Supported levels: {', '.join(MODEL_CONFIG)}"
        )

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is missing. "
            "Configure it in your environment variables."
        )

    model_name = MODEL_CONFIG[level]

    return ChatGroq(
        model=model_name,
        temperature=0,
        api_key=api_key,
    )


# ==================================================
# LOCAL MODEL TEST
# ==================================================

if __name__ == "__main__":

    print("Testing Groq LLM configuration...")

    llm = pick_llm("low")

    print(f"Selected model: {MODEL_CONFIG['low']}")

    response = llm.invoke(
        "What is the capital of France?"
    )

    print("\nModel response:")
    print(response.content)

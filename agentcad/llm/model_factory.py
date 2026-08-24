from __future__ import annotations

import os

from agentcad.config.settings import EngineSettings


class ModelFactory:
    """Creates LangChain chat-model instances while hiding provider specifics."""

    @staticmethod
    def create(settings: EngineSettings):
        provider = settings.llm_provider.lower().strip()
        model_name = settings.llm_model.strip()

        if provider == "openrouter":
            if not os.getenv("OPENROUTER_API_KEY"):
                raise RuntimeError("OPENROUTER_API_KEY is not set.")
            from langchain_openrouter import ChatOpenRouter
            return ChatOpenRouter(
                model=model_name,
                temperature=settings.llm_temperature,
                app_title="AgentCAD v3",
            )

        if provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY is not set.")
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_name, temperature=settings.llm_temperature)

        raise ValueError(f"Unsupported LLM provider: {provider}")


def create_chat_model(settings: EngineSettings):
    return ModelFactory.create(settings)

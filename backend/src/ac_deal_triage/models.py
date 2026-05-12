"""Model configuration. All LLM calls route through `chat_model`.

Configure via env:
  OPENAI_MODEL      model id, default "openai:gpt-4.1-mini"
  OPENAI_API_KEY    bearer (read by the OpenAI SDK natively)
  OPENAI_BASE_URL   endpoint URL; unset = OpenAI, set = any OpenAI-compatible
                    server (vLLM, Together, a hosted fine-tuned model).

Point `OPENAI_BASE_URL` at a fine-tuned model served behind any
OpenAI-compatible endpoint and no other code changes are needed.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model

DEFAULT_MODEL: str = os.getenv("OPENAI_MODEL", "openai:gpt-4.1-mini")
DEFAULT_MAX_RETRIES: int = int(os.getenv("OPENAI_MAX_RETRIES", "3"))

chat_model = init_chat_model(DEFAULT_MODEL, max_retries=DEFAULT_MAX_RETRIES)

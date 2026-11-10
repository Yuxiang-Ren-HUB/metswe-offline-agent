"""Local-backend compatibility: Ollama rejects chat messages whose content is null.

OpenAI-style requests allow `content: null` on assistant messages that only carry tool calls; vLLM (the Kaggle
scorer) accepts them, Ollama answers 400 "invalid message content type: <nil>" and the task dies. Replacing null
with "" changes nothing the model sees. Import and call install() before building the evaluator.
"""
from google.adk.models import lite_llm


def _clean(messages):
    for m in messages or []:
        if isinstance(m, dict):
            if m.get("content") is None:
                m["content"] = ""
        elif getattr(m, "content", "x") is None:
            try:
                m.content = ""
            except Exception:
                pass
    return messages


def install():
    cls = lite_llm.LiteLLMClient
    if getattr(cls, "_ollama_compat", False):
        return
    orig = cls.acompletion

    async def acompletion(self, model, messages, tools, **kwargs):
        return await orig(self, model, _clean(messages), tools, **kwargs)

    cls.acompletion = acompletion
    cls._ollama_compat = True

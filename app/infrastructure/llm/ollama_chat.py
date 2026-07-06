import ollama

from app.infrastructure.llm.ollama_opts import KEEP_ALIVE, opts


class OllamaChatResponder:
    """ChatResponder 포트의 Ollama 구현. 자유 텍스트 응답(정보/잡담)."""

    def __init__(self, host: str, model: str):
        self._client = ollama.AsyncClient(host=host)
        self._model = model

    async def respond(self, messages: list[dict]) -> str:
        resp = await self._client.chat(
            model=self._model,
            messages=messages,
            options=opts(0.7, num_predict=400),
            keep_alive=KEEP_ALIVE,
        )
        return resp["message"]["content"]

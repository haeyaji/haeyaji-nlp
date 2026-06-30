import ollama


class OllamaChatResponder:
    """ChatResponder 포트의 Ollama 구현. 자유 텍스트 응답(정보/잡담)."""

    def __init__(self, host: str, model: str):
        self._client = ollama.AsyncClient(host=host)
        self._model = model

    async def respond(self, messages: list[dict]) -> str:
        resp = await self._client.chat(
            model=self._model,
            messages=messages,
            options={"temperature": 0.7},
        )
        return resp["message"]["content"]

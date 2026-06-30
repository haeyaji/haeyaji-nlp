from fastapi import FastAPI

from app.api.message_router import router as message_router

app = FastAPI(title="todo-nlp", description="할일 추천 두뇌 (인텐트 라우팅 + RAG + LLM)")

app.include_router(message_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

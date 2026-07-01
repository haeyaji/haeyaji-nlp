from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.message_router import router as message_router
from app.config import settings

app = FastAPI(title="todo-nlp", description="할일 추천 두뇌 (인텐트 라우팅 + RAG + LLM)")

# fe 직접 연결(dev)용 CORS. be 경유 프로덕션에선 서버간 호출이라 불필요.
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(message_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

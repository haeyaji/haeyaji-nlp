from fastapi import APIRouter, Depends

from app.api.schemas import MessageRequest, MessageResponse
from app.application.message_service import MessageService
from app.deps import get_message_service

router = APIRouter(prefix="/api", tags=["message"])


@router.post("/message", response_model=MessageResponse)
async def message(
    req: MessageRequest,
    service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    return await service.handle(req)

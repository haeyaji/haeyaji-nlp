import asyncio

from app.api.schemas import MessageRequest, MessageResponse
from app.application.port.chat_responder import ChatResponder
from app.application.port.place_finder import PlaceFinder
from app.application.query_mapper import pick_search_queries
from app.domain.models import Place
from app.infrastructure.llm.prompt import build_info_messages


class InfoHandler:
    """정보 인텐트: 날씨/주변 장소 등 '아는 정보'로만 답하고, 모르는 건 솔직히."""

    def __init__(
        self,
        place_finder: PlaceFinder,
        responder: ChatResponder,
        default_radius_m: int,
    ):
        self._places = place_finder
        self._responder = responder
        self._default_radius = default_radius_m

    async def handle(self, req: MessageRequest) -> MessageResponse:
        radius = req.radius_m or self._default_radius

        # 장소 관련 질문일 수 있으니 주변 장소를 맥락으로 제공 (가볍게 3개씩)
        # 분류기가 뽑은 키워드 우선, 없으면 날씨·기분 규칙
        queries = req.search_keywords or pick_search_queries(req.weather, req.mood, req.text) or ["카페"]
        results = await asyncio.gather(
            *(
                self._places.search(q, req.lat, req.lng, radius, 3, sort=req.search_sort)
                for q in queries
            )
        )
        places: list[Place] = []
        seen: set[str] = set()
        for place_list in results:
            for p in place_list:
                if p.name not in seen:
                    seen.add(p.name)
                    places.append(p)

        reply = await self._responder.respond(
            build_info_messages(
                text=req.text,
                weather=req.weather,
                places=places,
                history=req.history,
            )
        )
        return MessageResponse(intent="info", reply=reply, todos=[])

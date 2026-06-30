import ollama
from pydantic import BaseModel

from app.domain.models import (
    Category,
    Place,
    TodoItem,
    TodoRecommendation,
    Turn,
    UserProfile,
)
from app.infrastructure.llm.prompt import build_messages


# LLM이 생성하는 초안(좌표 없음). 좌표/거리/url은 코드가 실제 Place에서 채운다.
class _DraftTodo(BaseModel):
    title: str
    reason: str
    category: Category
    estimated_minutes: int
    place_name: str | None = None


class _DraftRecommendation(BaseModel):
    analysis: str
    todos: list[_DraftTodo]


def _loose_match(name: str, places: list[Place]) -> Place | None:
    """LLM이 이름을 살짝 줄여/바꿔 적었을 때 느슨하게 매칭."""
    for p in places:
        if name in p.name or p.name in name:
            return p
    return None


class OllamaRecommender:
    """Recommender 포트의 Ollama 구현.

    LLM은 '무엇을/어디서(place_name)'만 고르고, 좌표·거리·url은
    실제 카카오 Place에서 코드가 채운다(환각 방지 + 지도 마커용).
    """

    def __init__(self, host: str, model: str):
        self._client = ollama.AsyncClient(host=host)
        self._model = model
        self._schema = _DraftRecommendation.model_json_schema()

    async def recommend(
        self,
        *,
        weather: str,
        mood: str,
        time_of_day: str,
        weekday: str,
        places: list[Place],
        note: str = "",
        user_profile: UserProfile | None = None,
        history: list[Turn] | None = None,
    ) -> TodoRecommendation:
        messages = build_messages(
            weather=weather,
            mood=mood,
            time_of_day=time_of_day,
            weekday=weekday,
            places=places,
            note=note,
            user_profile=user_profile,
            history=history,
        )
        resp = await self._client.chat(
            model=self._model,
            messages=messages,
            format=self._schema,  # 초안 스키마 강제
            options={"temperature": 0.7},
        )
        draft = _DraftRecommendation.model_validate_json(resp["message"]["content"])
        return self._enrich(draft, places)

    @staticmethod
    def _enrich(draft: _DraftRecommendation, places: list[Place]) -> TodoRecommendation:
        by_name = {p.name: p for p in places}
        todos: list[TodoItem] = []
        for d in draft.todos:
            item = TodoItem(
                title=d.title,
                reason=d.reason,
                category=d.category,
                estimated_minutes=d.estimated_minutes,
                place_name=d.place_name,
            )
            if d.place_name:
                place = by_name.get(d.place_name) or _loose_match(d.place_name, places)
                if place is not None:
                    item.place_name = place.name
                    item.place_url = place.url or None
                    item.x = place.x
                    item.y = place.y
                    item.distance_m = place.distance_m
                else:
                    # 후보 목록에 없는 장소명 → 환각으로 보고 장소 연결 해제
                    item.place_name = None
            todos.append(item)
        return TodoRecommendation(analysis=draft.analysis, todos=todos)

import ollama
from pydantic import BaseModel

from app.domain.models import (
    Category,
    Place,
    RecommendationPlan,
    TodoItem,
    TodoRecommendation,
    Turn,
    UserProfile,
)
from app.infrastructure.llm.ollama_opts import KEEP_ALIVE, opts
from app.infrastructure.llm.prompt import build_messages, build_rag_messages


# RAG 모드에서 LLM이 생성하는 초안 — place_name은 후보 목록의 이름이어야 한다.
# 좌표/거리/url은 LLM이 아니라 코드가 후보(Place)에서 채운다.
class _RagDraftTodo(BaseModel):
    title: str
    reason: str
    category: Category
    estimated_minutes: int
    place_name: str


class _RagDraft(BaseModel):
    analysis: str
    todos: list[_RagDraftTodo]


def _loose_match(name: str, places: list[Place]) -> Place | None:
    """LLM이 이름을 살짝 줄여/바꿔 적었을 때 느슨하게 매칭."""
    for p in places:
        if name in p.name or p.name in name:
            return p
    return None


class OllamaRecommender:
    """Recommender 포트의 Ollama 구현. 두 가지 모드:

    - recommend(계획 모드): '무엇을 할지 + 검색어'만 계획. 장소는 핸들러가 검색해 부착.
      (막연한 요청 — 검색어를 모르므로 계획이 먼저)
    - recommend_from_places(RAG 모드): 실제 후보 목록을 프롬프트에 주입하고
      그중에서 고르게 한다. 검색이 LLM 생성 품질을 올리는 진짜 RAG 경로.
      (검색어 확정 — 후보를 먼저 만들 수 있음)
    나중에 파인튜닝 모델로 바꾸려면 model 이름만 교체하면 된다.
    """

    def __init__(self, host: str, model: str):
        self._client = ollama.AsyncClient(host=host)
        self._model = model
        self._plan_schema = RecommendationPlan.model_json_schema()
        self._rag_schema = _RagDraft.model_json_schema()

    async def recommend(
        self,
        *,
        weather: str,
        mood: str,
        time_of_day: str,
        weekday: str,
        note: str = "",
        focus: str = "",
        user_profile: UserProfile | None = None,
        history: list[Turn] | None = None,
    ) -> RecommendationPlan:
        messages = build_messages(
            weather=weather,
            mood=mood,
            time_of_day=time_of_day,
            weekday=weekday,
            note=note,
            focus=focus,
            user_profile=user_profile,
            history=history,
        )
        resp = await self._client.chat(
            model=self._model,
            messages=messages,
            format=self._plan_schema,  # 계획 스키마 강제
            options=opts(0.5, num_predict=700),  # 검색어 채움 일관성 위해 약간 낮춤
            keep_alive=KEEP_ALIVE,
        )
        return RecommendationPlan.model_validate_json(resp["message"]["content"])

    async def recommend_from_places(
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
        messages = build_rag_messages(
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
            format=self._rag_schema,  # 후보 선택 스키마 강제
            options=opts(0.5, num_predict=700),
            keep_alive=KEEP_ALIVE,
        )
        draft = _RagDraft.model_validate_json(resp["message"]["content"])
        return self._attach(draft, places)

    @staticmethod
    def _attach(draft: _RagDraft, places: list[Place]) -> TodoRecommendation:
        """초안의 place_name을 실제 후보와 매칭해 좌표/거리/url을 채운다 (환각 가드).

        후보에 없는 이름이면 장소 연결을 해제하고, 같은 장소 중복 선택은 첫 번째만 인정.
        """
        by_name = {p.name: p for p in places}
        used: set[str] = set()
        todos: list[TodoItem] = []
        for d in draft.todos:
            item = TodoItem(
                title=d.title,
                reason=d.reason,
                category=d.category,
                estimated_minutes=d.estimated_minutes,
            )
            place = by_name.get(d.place_name) or _loose_match(d.place_name, places)
            if place is not None and place.name not in used:
                used.add(place.name)
                item.place_name = place.name
                item.place_url = place.url or None
                item.x = place.x
                item.y = place.y
                item.distance_m = place.distance_m
            todos.append(item)
        return TodoRecommendation(analysis=draft.analysis, todos=todos)

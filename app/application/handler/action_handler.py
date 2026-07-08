"""일정 생성/공유 액션 핸들러.

nlp는 '무엇을 하라'는 구조화된 Action을 만들 뿐, 실제 일정 저장·공유는 be가 한다.
활동이 명시된 경우(카페 등)만 실제 장소를 붙인 완전한 create 액션을 만든다(Mode A).
활동이 모호하면('뭐 할건데') 일단 추천만 하고, 사용자가 고른 뒤 be가 생성한다.
"""

from app.api.schemas import MessageRequest, MessageResponse
from app.application.action_rules import ActionParse
from app.application.handler.handler import Handler
from app.application.query_mapper import keyword_from_text
from app.domain.models import Action, TimeRange


def _time_label(tr: TimeRange | None) -> str:
    if tr is None:
        return ""
    if tr.raw:
        return tr.raw
    if tr.end_hour is not None:
        return f"{tr.start_hour}시~{tr.end_hour}시"
    return f"{tr.start_hour}시"


class ActionHandler:
    """행위 요청(일정 생성/공유)을 구조화 Action + 확인 문구로 변환."""

    def __init__(self, recommend_handler: Handler):
        self._recommend = recommend_handler

    async def handle(self, req: MessageRequest, parse: ActionParse) -> MessageResponse:
        actions: list[Action] = []
        todos = []
        reply_parts: list[str] = []
        when = _time_label(parse.time_range)

        if parse.create:
            kw = keyword_from_text(req.text)
            if kw is not None:
                # 활동 명시 → 실제 장소 하나 붙여 완전한 create 액션
                rec = await self._recommend.handle(
                    req.model_copy(update={"search_keywords": [kw]})
                )
                todos = rec.todos
                top = rec.todos[0] if rec.todos else None
                actions.append(
                    Action(
                        type="schedule.create",
                        time_range=parse.time_range,
                        title=(top.title if top else kw),
                        place_name=(top.place_name if top else None),
                        place_url=(top.place_url if top else None),
                    )
                )
                place = f" {top.place_name}" if (top and top.place_name) else ""
                head = f"{when} " if when else ""
                reply_parts.append(f"{head}{kw}{place} 일정을 추가할게요.")
            else:
                # 활동 모호 → Mode A: 일단 추천만, 사용자가 고르면 be가 생성
                rec = await self._recommend.handle(req)
                todos = rec.todos
                head = f"{when}에 " if when else ""
                reply_parts.append(f"{head}뭐 할지 아래에서 골라주시면 일정에 넣어드릴게요.")

        if parse.share:
            actions.append(
                Action(
                    type="schedule.share",
                    target_friend=parse.target_friend,
                    ref="$lastCreated" if parse.create else None,
                )
            )
            who = f"{parse.target_friend}님" if parse.target_friend else "친구"
            reply_parts.append(f"{who}과 공유할게요.")

        return MessageResponse(
            intent="action",
            reply=" ".join(reply_parts).strip(),
            todos=todos,
            actions=actions,
        )

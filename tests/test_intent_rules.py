from app.application.intent_rules import rule_intent


def test_coding_request_to_chat():
    assert rule_intent("파이썬으로 퀵소트 짜줘") == "chat"


def test_recipe_to_chat():
    assert rule_intent("김치찌개 레시피 추천해줘") == "chat"


def test_normal_requests_defer_to_llm():
    assert rule_intent("비 오는데 뭐하지") is None
    assert rule_intent("강남역 맛집 추천") is None

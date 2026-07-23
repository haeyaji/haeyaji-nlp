from app.application.category_map import (
    ALL_CODES,
    default_keywords_for,
    label_for,
    queries_for,
)
from app.domain.models import Category
from typing import get_args


def test_all_codes_match_domain_category_literal():
    # category_map의 10종과 도메인 Category Literal이 정확히 일치
    assert set(ALL_CODES) == set(get_args(Category))


def test_every_code_has_label_queries_keywords():
    for code in ALL_CODES:
        assert label_for(code)
        assert queries_for(code)          # 2단계 검색어 최소 1개
        assert default_keywords_for(code)


def test_unknown_code_is_empty():
    assert queries_for("NOPE") == []
    assert default_keywords_for("NOPE") == []

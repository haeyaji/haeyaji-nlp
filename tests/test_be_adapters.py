import asyncio

import httpx

from app.infrastructure.be.be_geocoder import BeGeocoder
from app.infrastructure.be.be_place_finder import BePlaceFinder

_BASE = "http://be.test"


def _client(handler) -> httpx.AsyncClient:
    """MockTransport로 be 응답을 흉내내는 AsyncClient."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---- BePlaceFinder ----

def test_place_search_maps_camel_response_to_place():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/places/search"
        qp = req.url.params
        assert qp["query"] == "맛집"
        assert qp["radiusM"] == "1500"
        assert qp["sort"] == "distance"
        assert qp["categoryGroupCode"] == "FD6"
        return httpx.Response(
            200,
            json={"places": [
                {"name": "김밥천국", "category": "음식점", "address": "서울 강남",
                 "url": "http://place/1", "distanceM": 120, "x": 127.03, "y": 37.5},
            ]},
        )

    finder = BePlaceFinder(base_url=_BASE, client=_client(handler))
    places = asyncio.run(finder.search(
        "맛집", lat=37.5, lng=127.0, radius_m=1500, sort="distance", category_group_code="FD6"
    ))
    assert len(places) == 1
    p = places[0]
    assert p.name == "김밥천국"
    assert p.distance_m == 120  # distanceM → distance_m 매핑
    assert p.x == 127.03 and p.y == 37.5


def test_place_search_handles_missing_and_null_fields():
    def handler(req: httpx.Request) -> httpx.Response:
        # distanceM/x/y 없음 → None 으로 안전 매핑
        return httpx.Response(200, json={"places": [{"name": "무명카페", "category": "카페", "address": "어딘가"}]})

    finder = BePlaceFinder(base_url=_BASE, client=_client(handler))
    places = asyncio.run(finder.search("카페", lat=37.5, lng=127.0, radius_m=1000))
    assert places[0].distance_m is None
    assert places[0].x is None and places[0].y is None
    assert places[0].url == ""


def test_place_search_returns_empty_on_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    finder = BePlaceFinder(base_url=_BASE, client=_client(handler))
    assert asyncio.run(finder.search("맛집", lat=37.5, lng=127.0, radius_m=1000)) == []


def test_place_search_omits_category_code_when_none():
    def handler(req: httpx.Request) -> httpx.Response:
        assert "categoryGroupCode" not in req.url.params  # None이면 파라미터 자체를 안 보냄
        return httpx.Response(200, json={"places": []})

    finder = BePlaceFinder(base_url=_BASE, client=_client(handler))
    assert asyncio.run(finder.search("놀거리", lat=37.5, lng=127.0, radius_m=1000)) == []


# ---- BeGeocoder ----

def test_geocode_returns_lat_lng():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/places/geocode"
        assert req.url.params["query"] == "강남역"
        return httpx.Response(200, json={"lat": 37.4979, "lng": 127.0276})

    geo = BeGeocoder(base_url=_BASE, client=_client(handler))
    assert asyncio.run(geo.geocode("강남역")) == (37.4979, 127.0276)


def test_geocode_204_returns_none():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    geo = BeGeocoder(base_url=_BASE, client=_client(handler))
    assert asyncio.run(geo.geocode("없는지역")) is None


def test_geocode_returns_none_on_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(502)

    geo = BeGeocoder(base_url=_BASE, client=_client(handler))
    assert asyncio.run(geo.geocode("강남역")) is None

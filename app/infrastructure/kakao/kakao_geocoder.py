import httpx

_KAKAO_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoGeocoder:
    """Geocoder 포트의 카카오 구현. 키워드 검색 top1의 좌표를 반환.

    실패/미발견 시 None → 호출측이 현재 위치로 폴백 (graceful).
    """

    def __init__(self, rest_key: str, timeout: float = 5.0):
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"KakaoAK {rest_key}"}, timeout=timeout
        )

    async def geocode(self, query: str) -> tuple[float, float] | None:
        try:
            resp = await self._client.get(_KAKAO_URL, params={"query": query, "size": 1})
            resp.raise_for_status()
            docs = resp.json().get("documents", [])
        except (httpx.HTTPError, ValueError):
            return None
        if not docs:
            return None
        d = docs[0]
        try:
            return (float(d["y"]), float(d["x"]))  # (위도, 경도)
        except (KeyError, TypeError, ValueError):
            return None

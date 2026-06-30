from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수에서 설정 로드 (.env 지원)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 카카오 로컬 API
    kakao_rest_key: str = ""

    # Ollama (한국어 특화 EXAONE 기본. 약한 PC는 exaone3.5:2.4b 로 .env에서 교체)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "exaone3.5:7.8b"

    # 추천 기본값
    default_radius_m: int = 1500
    places_per_query: int = 5

    # 로그
    log_dir: str = "data/logs"


settings = Settings()

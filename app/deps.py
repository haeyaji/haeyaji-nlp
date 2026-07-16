from functools import lru_cache

from app.application.handler.action_handler import ActionHandler
from app.application.handler.chat_handler import ChatHandler
from app.application.handler.info_handler import InfoHandler
from app.application.handler.recommend_handler import RecommendHandler
from app.application.message_service import MessageService
from app.config import settings
from app.infrastructure.be.be_geocoder import BeGeocoder
from app.infrastructure.be.be_place_finder import BePlaceFinder
from app.infrastructure.llm.ollama_chat import OllamaChatResponder
from app.infrastructure.llm.ollama_classifier import OllamaIntentClassifier
from app.infrastructure.llm.ollama_recommender import OllamaRecommender


@lru_cache  # 앱 수명 동안 1회 생성 (싱글톤)
def get_message_service() -> MessageService:
    place_finder = BePlaceFinder(base_url=settings.be_base_url)
    geocoder = BeGeocoder(base_url=settings.be_base_url)
    recommender = OllamaRecommender(host=settings.ollama_host, model=settings.ollama_model)
    classifier = OllamaIntentClassifier(host=settings.ollama_host, model=settings.ollama_model)
    responder = OllamaChatResponder(host=settings.ollama_host, model=settings.ollama_model)

    recommend_handler = RecommendHandler(
        place_finder=place_finder,
        recommender=recommender,
        default_radius_m=settings.default_radius_m,
        places_per_query=settings.places_per_query,
    )

    return MessageService(
        classifier=classifier,
        geocoder=geocoder,
        recommend_handler=recommend_handler,
        info_handler=InfoHandler(
            place_finder=place_finder,
            responder=responder,
            default_radius_m=settings.default_radius_m,
        ),
        chat_handler=ChatHandler(responder=responder),
        action_handler=ActionHandler(recommend_handler=recommend_handler),
    )

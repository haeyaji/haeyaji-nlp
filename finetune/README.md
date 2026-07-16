# finetune (미래)

지금은 비어 있음. **프롬프트 + RAG로 충분한 단계**라 파인튜닝은 아직 하지 않는다.

## 언제 시작하나

좋은 추천 사례 + 사용자 피드백이 수백~수천 건 쌓이고,
프롬프트만으로 일관성/품질의 한계가 보일 때.

> **학습 데이터 원천 = be.** nlp는 stateless라 상호작용을 저장하지 않는다(PRD §2:
> "nlp는 실행/저장을 하지 않는다"). 추천 요청·응답·피드백 로깅은 게이트웨이이자
> 진실 원천인 be가 담당하고, 학습셋은 be에서 export 받아 온다.

## 계획 (그때)

1. `prepare_data.py` — be가 export한 상호작용 로그(JSONL) → SFT 학습셋(JSONL) 변환
2. `train_lora.py` — Colab 무료 GPU + HuggingFace TRL `SFTTrainer` + LoRA
3. 결과 LoRA 어댑터를 HuggingFace Hub에 push → 팀 공유
4. 서빙: `OllamaRecommender`의 모델만 교체하거나, peft로 base+adapter 로드
   (포트 `Recommender` 인터페이스는 그대로 유지)

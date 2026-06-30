# finetune (미래)

지금은 비어 있음. **프롬프트 + RAG로 충분한 단계**라 파인튜닝은 아직 하지 않는다.

## 언제 시작하나

`data/logs/interactions.jsonl`에 좋은 추천 사례 + 사용자 피드백이 수백~수천 건 쌓이고,
프롬프트만으로 일관성/품질의 한계가 보일 때.

## 계획 (그때)

1. `prepare_data.py` — `interactions.jsonl` → SFT 학습셋(JSONL) 변환
2. `train_lora.py` — Colab 무료 GPU + HuggingFace TRL `SFTTrainer` + LoRA
3. 결과 LoRA 어댑터를 HuggingFace Hub에 push → 팀 공유
4. 서빙: `OllamaRecommender`의 모델만 교체하거나, peft로 base+adapter 로드
   (포트 `Recommender` 인터페이스는 그대로 유지)

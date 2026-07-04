"""
rag/sentiment_ml.py — ML 증류 감성 모델 추론

train_sentiment_model.py가 LLM 라벨로 학습해 저장한 모델(sentiment_model.joblib)을
불러와, 새 기사의 감성 점수(-1~1)를 LLM 없이 즉시·무료·일관되게 예측한다.

  · 모델 파일이 없으면 None 반환 → 호출부가 단어 사전으로 폴백 가능
  · 모델은 한 번만 로드해 캐시
"""

from pathlib import Path

import joblib

MODEL_PATH = Path(__file__).resolve().parent / "sentiment_model.joblib"
BODY_CHARS = 500

_model = None
_load_failed = False


def _load():
    global _model, _load_failed
    if _model is None and not _load_failed:
        try:
            _model = joblib.load(MODEL_PATH)
        except Exception:
            _load_failed = True   # 모델 파일 없음/손상 → 폴백 신호
    return _model


def predict_sentiment(title: str, content: str) -> float | None:
    """기사 감성 점수(-1.0~+1.0) 예측. 모델이 없으면 None."""
    model = _load()
    if model is None:
        return None
    text = f"{title or ''} {(content or '')[:BODY_CHARS]}".strip()
    if not text:
        return 0.0
    score = float(model.predict([text])[0])
    return max(-1.0, min(1.0, score))

"""
train_sentiment_model.py — LLM 감성 라벨을 정답으로 가벼운 ML 감성 모델 학습 (ML 증류)

LLM(gpt-4o-mini)이 매긴 articles.sentiment(-1~1)를 정답지로,
TF-IDF(문자 n-gram) + Ridge 회귀를 학습한다. 이후 새 기사는 LLM 없이
이 모델로 즉시·무료·일관되게 감성 점수를 매길 수 있다.

  · 한국어는 띄어쓰기가 불규칙해 단어 토큰 대신 '문자 n-gram'(char_wb 2~4)을 사용
  · 회귀로 연속 점수(-1~1) 예측 → 부호(호재/악재)가 핵심 지표

실행:
    python train_sentiment_model.py
산출물:
    rag/sentiment_model.joblib  (학습된 파이프라인)
    + 콘솔에 검증 리포트 (부호 일치율 / MAE / 상관)
"""

import sqlite3
from pathlib import Path

import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "identifier.sqlite"
MODEL_PATH = BASE / "rag" / "sentiment_model.joblib"
BODY_CHARS = 500
NEG_WEIGHT = 3.5   # 악재 샘플 가중치 (호재:악재 ≈ 3.5:1 불균형 보정)


def _sample_weights(y: np.ndarray) -> np.ndarray:
    """악재(y<0) 샘플에 NEG_WEIGHT 배 가중치를 줘 불균형 보정."""
    w = np.ones(len(y))
    w[y < 0] = NEG_WEIGHT
    return w


def load_data():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT title, content, sentiment FROM articles WHERE sentiment IS NOT NULL"
        ).fetchall()
    texts = [f"{(t or '')} {(c or '')[:BODY_CHARS]}".strip() for t, c, _ in rows]
    y = np.array([float(s) for _, _, s in rows])
    return texts, y


def build_model() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                                  min_df=3, max_features=50000)),
        ("reg", Ridge(alpha=1.0)),
    ])


def report(name, y_true, y_pred):
    mae = np.mean(np.abs(y_true - y_pred))
    corr = np.corrcoef(y_true, y_pred)[0, 1]
    mask = y_true != 0
    sign_acc = np.mean((y_pred[mask] > 0) == (y_true[mask] > 0))
    # 클래스별 재현율 (불균형 보정 효과 확인용)
    pos, neg = y_true > 0, y_true < 0
    pos_rec = (y_pred[pos] > 0).mean() * 100 if pos.any() else 0.0
    neg_rec = (y_pred[neg] < 0).mean() * 100 if neg.any() else 0.0
    print(f"  [{name}] MAE {mae:.3f} | 상관 {corr:.3f} | 부호일치 {sign_acc*100:.1f}% "
          f"| 호재재현 {pos_rec:.1f}% | 악재재현 {neg_rec:.1f}%")
    return sign_acc


def main():
    print("■ 데이터 로드...")
    texts, y = load_data()
    print(f"  학습 데이터: {len(texts)}건 (호재 {int((y>0).sum())} / "
          f"악재 {int((y<0).sum())} / 중립 {int((y==0).sum())})")

    Xtr, Xte, ytr, yte = train_test_split(texts, y, test_size=0.2, random_state=42)

    print(f"■ 학습 중 (TF-IDF char 2~4gram + Ridge, 악재가중 {NEG_WEIGHT})...")
    model = build_model()
    model.fit(Xtr, ytr, reg__sample_weight=_sample_weights(ytr))

    print("■ 검증 — ML이 LLM을 얼마나 잘 따라하나:")
    report("train", ytr, model.predict(Xtr))
    report("test ", yte, model.predict(Xte))

    # 전체로 재학습 후 저장 (배포용)
    print("■ 전체 데이터로 재학습 후 저장...")
    final = build_model()
    final.fit(texts, y, reg__sample_weight=_sample_weights(y))
    joblib.dump(final, MODEL_PATH)
    print(f"  저장: {MODEL_PATH}")

    # 영향력 큰 단어(특징) 엿보기 — 투명성 확인
    print("■ 모델이 배운 악재/호재 신호 (상위 char n-gram 일부):")
    vec = final.named_steps["tfidf"]
    coef = final.named_steps["reg"].coef_
    feats = np.array(vec.get_feature_names_out())
    top_neg = feats[np.argsort(coef)[:12]]
    top_pos = feats[np.argsort(coef)[-12:]]
    print(f"    악재 신호: {', '.join(repr(f) for f in top_neg)}")
    print(f"    호재 신호: {', '.join(repr(f) for f in top_pos)}")


if __name__ == "__main__":
    main()

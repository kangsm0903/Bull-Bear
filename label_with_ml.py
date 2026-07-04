"""
label_with_ml.py — ML 증류 모델로 기사 감성 점수를 sentiment_ml 컬럼에 채움

LLM 정답지(sentiment 컬럼)는 건드리지 않고, 별도 sentiment_ml 컬럼에 ML 예측을 저장한다.
  · 미라벨(sentiment IS NULL) 기사 → ML이 LLM 대신 라벨링한 결과
  · LLM 라벨된 기사            → ML vs LLM 비교용 (같은 행에 두 점수 공존)

ML 추론은 로컬·무료라 전체 일괄 예측(model.predict)으로 수 초 내 완료.

실행:
    python label_with_ml.py
"""

import sqlite3
from pathlib import Path

import numpy as np

from rag.sentiment_ml import _load, BODY_CHARS

DB_PATH = Path(__file__).resolve().parent / "identifier.sqlite"


def ensure_column(conn) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()]
    if "sentiment_ml" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN sentiment_ml REAL")
        conn.commit()
        print("  sentiment_ml 컬럼 생성")


def main():
    model = _load()
    if model is None:
        print("ML 모델(rag/sentiment_model.joblib)이 없습니다. 먼저 학습하세요.")
        return

    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        ensure_column(conn)

        rows = conn.execute(
            "SELECT id, title, content FROM articles WHERE title IS NOT NULL"
        ).fetchall()
        print(f"■ 대상: {len(rows):,}건 — ML 점수 일괄 예측 중...")

        texts = [f"{(t or '')} {(c or '')[:BODY_CHARS]}".strip() for _, t, c in rows]
        preds = np.clip(model.predict(texts), -1.0, 1.0)

        conn.executemany(
            "UPDATE articles SET sentiment_ml = ? WHERE id = ?",
            [(float(p), rid) for (rid, *_), p in zip(rows, preds)],
        )
        conn.commit()
        print(f"  저장 완료: {len(rows):,}건 → sentiment_ml")

        # ── ML vs LLM 일치 비교 (LLM 라벨 있는 행만) ──
        comp = conn.execute(
            "SELECT sentiment, sentiment_ml FROM articles "
            "WHERE sentiment IS NOT NULL AND sentiment != 0"
        ).fetchall()
        if comp:
            llm = np.array([r[0] for r in comp])
            ml = np.array([r[1] for r in comp])
            sign_match = np.mean((llm > 0) == (ml > 0)) * 100
            mae = np.mean(np.abs(llm - ml))
            print(f"\n■ ML vs LLM (정답 있는 {len(comp):,}건, 중립 제외):")
            print(f"    부호 일치율: {sign_match:.1f}%  |  MAE: {mae:.3f}")


if __name__ == "__main__":
    main()

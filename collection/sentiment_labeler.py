"""
collection/sentiment_labeler.py — LLM 기사 감성 라벨링 (인덱싱 시점, 1회성)

단어 사전(rag/sentiment.py)이 놓치는 미묘한 악재·반어를 LLM(gpt-4o-mini)이 맥락으로 채점해
articles.sentiment 컬럼에 미리 저장한다. 토론 런타임은 이 값을 읽기만 하므로 비용 0.

  · sentiment IS NULL 인 기사만 처리 → 재실행/신규기사 대응
  · 배치(기본 10개)로 묶어 호출 → 비용·속도 절감

실행:
    python -m collection.sentiment_labeler              # 전체 (NULL인 기사 모두)
    python -m collection.sentiment_labeler --ticker 005930   # 특정 종목만 (테스트)
    python -m collection.sentiment_labeler --limit 50        # 최대 N건만 (테스트)
"""

import argparse
import json
import sqlite3
import time
from pathlib import Path

from openai import RateLimitError

from rag.embedder import get_client
from agents.config import SENTIMENT_MODEL

DB_PATH = Path(__file__).resolve().parent.parent / "identifier.sqlite"

BATCH_SIZE   = 10     # 한 번에 채점할 기사 수
BODY_CHARS   = 200    # 기사 본문은 앞 N자만 사용 (토큰 절약)
MAX_RETRIES  = 6      # RateLimit 재시도 횟수

SYSTEM_PROMPT = (
    "당신은 주식 투자 뉴스 감성 분석가입니다. "
    "각 기사가 해당 종목의 주가에 호재(긍정)인지 악재(부정)인지 투자 관점에서 판단합니다."
)


def ensure_sentiment_column() -> None:
    """articles 테이블에 sentiment REAL 컬럼이 없으면 추가."""
    with sqlite3.connect(DB_PATH) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()]
        if "sentiment" not in cols:
            conn.execute("ALTER TABLE articles ADD COLUMN sentiment REAL")
            conn.commit()
            print("✅ articles.sentiment 컬럼 추가 완료")


def _build_user_prompt(batch: list[dict]) -> str:
    lines = [
        "다음 기사들을 투자 관점에서 채점하세요. "
        "호재(긍정)면 양수, 악재(부정)면 음수, 중립이면 0으로, -1.0 ~ +1.0 사이 실수로 매깁니다.\n"
    ]
    for i, a in enumerate(batch):
        body = (a.get("content") or "")[:BODY_CHARS].replace("\n", " ")
        lines.append(f"[{i}] 제목: {a.get('title', '')}\n     내용: {body}")
    lines.append(
        '\n반드시 JSON으로만 응답하세요: '
        '{"scores": [{"idx": 0, "sentiment": -0.5}, {"idx": 1, "sentiment": 0.7}, ...]}'
    )
    return "\n".join(lines)


def label_batch(client, batch: list[dict]) -> dict[int, float]:
    """배치 기사를 LLM으로 채점해 {idx: sentiment(-1~1)} 반환. 실패 시 빈 dict."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=SENTIMENT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": _build_user_prompt(batch)},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            data = json.loads(resp.choices[0].message.content)
            out: dict[int, float] = {}
            for item in data.get("scores", []):
                idx = int(item["idx"])
                val = max(-1.0, min(1.0, float(item["sentiment"])))
                out[idx] = val
            return out
        except RateLimitError:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 5 * (attempt + 1)
            print(f"\n  ⚠️  Rate limit — {wait}초 대기 후 재시도 ({attempt + 1}/{MAX_RETRIES - 1})")
            time.sleep(wait)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            print(f"\n  ⚠️  배치 파싱 실패(건너뜀, 다음 실행에 재처리): {e}")
            return {}
    return {}


def main(only_ticker: str = None, limit: int = None, batch_size: int = BATCH_SIZE):
    ensure_sentiment_column()
    client = get_client()

    query = "SELECT id, title, content FROM articles WHERE sentiment IS NULL"
    params: tuple = ()
    if only_ticker:
        query += " AND ticker = ?"
        params = (only_ticker,)
    query += " ORDER BY published_at DESC"
    if limit:
        query += f" LIMIT {int(limit)}"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    total = len(rows)
    if total == 0:
        print("라벨링 대상 없음 (모두 처리됨).")
        return

    print(f"라벨링 대상: {total}건 | 모델: {SENTIMENT_MODEL} | 배치 {batch_size}\n")
    done = 0
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        for i in range(0, total, batch_size):
            batch = rows[i:i + batch_size]
            scores = label_batch(client, batch)
            for j, a in enumerate(batch):
                s = scores.get(j)
                if s is not None:
                    conn.execute("UPDATE articles SET sentiment = ? WHERE id = ?", (s, a["id"]))
            conn.commit()
            done += len(batch)
            print(f"  진행: {done}/{total}", end="\r")

    print(f"\n🎉 완료: {done}건 처리")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM 기사 감성 라벨링")
    parser.add_argument("--ticker", default=None, help="특정 종목만 (예: 005930)")
    parser.add_argument("--limit",  type=int, default=None, help="최대 N건만 (테스트)")
    args = parser.parse_args()
    main(only_ticker=args.ticker, limit=args.limit)

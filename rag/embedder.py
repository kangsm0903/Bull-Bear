"""
OpenAI text-embedding-3-small 래퍼

차원: 1536
비용: $0.02 / 1M tokens (전체 데이터 기준 약 19원)
속도 제한: 3,000 RPM (사실상 제한 없음)
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_client = None

MODEL = "text-embedding-3-small"  # 1536차원
BATCH_SIZE = 100                   # 한 번에 처리할 텍스트 수 (최대 2048)
MAX_RETRIES = 6                    # TPM(분당 토큰) 한도 초과 시 배치 재시도 횟수


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(".env에 OPENAI_API_KEY가 설정되지 않았습니다.")
        _client = OpenAI(api_key=api_key)
    return _client


def _embed_batch_with_retry(client: OpenAI, batch: list[str]):
    """단일 배치 임베딩. TPM 한도 초과(429) 시 backoff 후 재시도."""
    for attempt in range(MAX_RETRIES):
        try:
            return client.embeddings.create(input=batch, model=MODEL)
        except RateLimitError:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 5 * (attempt + 1)  # 5, 10, 15, 20, 25초
            print(f"\n  ⚠️  Rate limit(TPM) — {wait}초 대기 후 재시도 "
                  f"({attempt + 1}/{MAX_RETRIES - 1})")
            time.sleep(wait)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """문서 텍스트 리스트 → 벡터 리스트 (배치 처리)"""
    client = get_client()
    all_embeddings = []
    total = len(texts)

    for i in range(0, total, BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        response = _embed_batch_with_retry(client, batch)
        all_embeddings.extend([item.embedding for item in response.data])

        done = min(i + BATCH_SIZE, total)
        remaining = total - done
        eta_sec = int(remaining / BATCH_SIZE * 0.5)  # 배치당 약 0.5초
        print(f"  임베딩 진행: {done}/{total}  (남은 예상 시간: {eta_sec//60}분 {eta_sec%60}초)", end="\r")

        if done < total:
            time.sleep(0.1)  # API 부하 방지용 최소 대기

    print()
    return all_embeddings


def embed_query(query: str) -> list[float]:
    """검색 쿼리 → 벡터 (단일, 실시간)"""
    client = get_client()
    response = client.embeddings.create(input=[query], model=MODEL)
    return response.data[0].embedding

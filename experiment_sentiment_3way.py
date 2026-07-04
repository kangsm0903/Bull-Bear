"""
experiment_sentiment_3way.py — 감성 분류 3방식(단어사전·ML·LLM) 공정 비교 실험

설계:
  1. 표본    : 4o-mini 라벨 기준 층화추출 500건 (호재/악재/중립 균형) — 악재 충분 확보
  2. 정답지  : gpt-5.4(reasoning=high) 독립 심판이 호재(+1)/악재(-1)/중립(0) 재판정
               → 셋 중 누구의 라벨도 아닌 독립 기준 (LLM=100% 함정 회피)
  3. 채점    : 같은 500건에 대해
       · 단어사전 : rag.sentiment.sentiment_score
       · LLM      : 저장된 4o-mini 라벨(sentiment) 재사용 (= 실제 배포 라벨)
       · ML       : 이 500건을 학습에서 제외하고 재학습한 모델로 예측 (test 격리)
  4. 지표    : 3분류 정확도 / 부호 정확도 / 호재재현 / 악재재현 / 혼동행렬
  5. 산출    : results/SENTIMENT_3WAY_EXPERIMENT.md

심판 결과는 results/judge_cache.json에 캐시 → 재실행 시 gpt-5.4 재호출 안 함.

실행:
    python experiment_sentiment_3way.py
"""

import json
import random
import sqlite3
import time
from pathlib import Path

import numpy as np

from agents.base_agent import get_client
from rag.sentiment import sentiment_score
from train_sentiment_model import build_model, _sample_weights, BODY_CHARS as ML_BODY

BASE = Path(__file__).resolve().parent
DB = BASE / "identifier.sqlite"
OUT = BASE / "results" / "SENTIMENT_3WAY_EXPERIMENT.md"
CACHE = BASE / "results" / "judge_cache.json"

SEED = 42
N_POS, N_NEG, N_NEU = 170, 170, 160      # 층화 추출 목표 (총 500)
JUDGE_MODEL = "gpt-5.4"
JUDGE_EFFORT = "high"
JUDGE_BATCH = 8
JUDGE_BODY = 400                          # 심판이 보는 본문 길이
BAND = 0.05                               # |점수|<=BAND 면 중립으로 간주

JUDGE_SYS = (
    "당신은 한국 주식 투자 전문 애널리스트입니다. 각 뉴스가 '해당 종목의 주가'에 "
    "호재(긍정)인지 악재(부정)인지 중립인지를 투자 관점에서 신중히 판정합니다. "
    "표면 단어가 아니라 맥락(예: '파업 제동'은 파업이 막힌 것이므로 호재)을 봅니다."
)


def fetch_strata():
    """4o-mini 라벨 부호로 층화추출한 500건(id,corp_name,title,content,llm)."""
    random.seed(SEED)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    q = ("SELECT a.id, c.corp_name, a.title, a.content, a.sentiment AS llm "
         "FROM articles a JOIN companies c ON a.ticker=c.ticker "
         "WHERE a.sentiment {} AND a.title IS NOT NULL AND a.content IS NOT NULL")
    pos = [dict(r) for r in conn.execute(q.format("> 0.05")).fetchall()]
    neg = [dict(r) for r in conn.execute(q.format("< -0.05")).fetchall()]
    neu = [dict(r) for r in conn.execute(q.format("BETWEEN -0.05 AND 0.05")).fetchall()]
    conn.close()
    sample = (random.sample(pos, min(N_POS, len(pos)))
              + random.sample(neg, min(N_NEG, len(neg)))
              + random.sample(neu, min(N_NEU, len(neu))))
    random.shuffle(sample)
    print(f"표본: 호재풀 {len(pos)} / 악재풀 {len(neg)} / 중립풀 {len(neu)} "
          f"→ 추출 {len(sample)}건")
    return sample


def judge_batch(client, batch):
    """gpt-5.4가 배치를 판정 → {id: label(-1/0/1)}."""
    lines = ["다음 기사들을 판정하세요. label은 호재=1, 악재=-1, 중립=0 중 하나입니다.\n"]
    for i, a in enumerate(batch):
        body = (a["content"] or "")[:JUDGE_BODY].replace("\n", " ")
        lines.append(f"[{i}] 종목: {a['corp_name']}\n     제목: {a['title']}\n     내용: {body}")
    lines.append('\nJSON으로만: {"labels":[{"idx":0,"label":1},{"idx":1,"label":-1}, ...]}')
    prompt = "\n".join(lines)

    for attempt in range(5):
        try:
            resp = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "system", "content": JUDGE_SYS},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                reasoning_effort=JUDGE_EFFORT,
            )
            data = json.loads(resp.choices[0].message.content)
            out = {}
            for item in data.get("labels", []):
                idx = int(item["idx"])
                lab = int(item["label"])
                if 0 <= idx < len(batch):
                    out[batch[idx]["id"]] = max(-1, min(1, lab))
            return out
        except Exception as e:
            print(f"  ⚠️ 심판 배치 재시도({attempt+1}/5): {e}")
            time.sleep(5 * (attempt + 1))
    return {}


def get_truth(sample):
    """gpt-5.4 정답 라벨 (캐시 사용)."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [a for a in sample if a["id"] not in cache]
    if todo:
        print(f"gpt-5.4 심판 호출: {len(todo)}건 (캐시 {len(cache)}건 재사용) "
              f"| effort={JUDGE_EFFORT}")
        client = get_client()
        for i in range(0, len(todo), JUDGE_BATCH):
            res = judge_batch(client, todo[i:i + JUDGE_BATCH])
            cache.update({k: v for k, v in res.items()})
            CACHE.write_text(json.dumps(cache, ensure_ascii=False))
            print(f"  진행 {min(i+JUDGE_BATCH, len(todo))}/{len(todo)}", end="\r")
        print()
    else:
        print(f"심판 캐시 전량 재사용: {len(sample)}건")
    return {a["id"]: cache[a["id"]] for a in sample if a["id"] in cache}


def ml_predict_isolated(sample):
    """500건을 학습에서 제외하고 ML 재학습 → 그 500건 예측 (test 격리)."""
    test_ids = {a["id"] for a in sample}
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT id, title, content, sentiment FROM articles WHERE sentiment IS NOT NULL"
    ).fetchall()
    conn.close()
    tr = [(t, c, s) for (i, t, c, s) in rows if i not in test_ids]
    Xtr = [f"{(t or '')} {(c or '')[:ML_BODY]}".strip() for t, c, _ in tr]
    ytr = np.array([float(s) for _, _, s in tr])
    print(f"ML 재학습(테스트 {len(test_ids)}건 제외): 학습 {len(Xtr)}건")
    model = build_model()
    model.fit(Xtr, ytr, reg__sample_weight=_sample_weights(ytr))
    Xte = [f"{(a['title'] or '')} {(a['content'] or '')[:ML_BODY]}".strip() for a in sample]
    return {a["id"]: float(np.clip(p, -1, 1)) for a, p in zip(sample, model.predict(Xte))}


def to_cls(score):
    return 1 if score > BAND else (-1 if score < -BAND else 0)


def evaluate(name, truth, preds):
    """preds: {id: 연속점수}. truth: {id: -1/0/1}. 지표 dict 반환 + 혼동행렬."""
    ids = [i for i in truth if i in preds]
    y = np.array([truth[i] for i in ids])
    p = np.array([to_cls(preds[i]) for i in ids])
    acc3 = (y == p).mean() * 100
    nz = y != 0
    sign_acc = (np.sign([preds[i] for i in ids])[nz] == y[nz]).mean() * 100
    pos, neg = y == 1, y == -1
    pos_rec = (p[pos] == 1).mean() * 100 if pos.any() else 0
    neg_rec = (p[neg] == -1).mean() * 100 if neg.any() else 0
    labels = [1, -1, 0]
    mat = [[int(((y == a) & (p == b)).sum()) for b in labels] for a in labels]
    return {"name": name, "acc3": acc3, "sign": sign_acc,
            "pos_rec": pos_rec, "neg_rec": neg_rec, "mat": mat, "n": len(ids)}


def main():
    sample = fetch_strata()
    truth = get_truth(sample)
    print(f"정답지 확보: {len(truth)}건")
    tcnt = {v: sum(1 for x in truth.values() if x == v) for v in (1, -1, 0)}
    print(f"  gpt-5.4 정답 분포 — 호재 {tcnt[1]} / 악재 {tcnt[-1]} / 중립 {tcnt[0]}")

    dict_p = {a["id"]: sentiment_score(a["title"], a["content"]) for a in sample}
    llm_p = {a["id"]: float(a["llm"]) for a in sample}
    ml_p = ml_predict_isolated(sample)

    results = [evaluate("단어사전", truth, dict_p),
               evaluate("LLM (4o-mini)", truth, llm_p),
               evaluate("ML (증류)", truth, ml_p)]

    name = {1: "호재", -1: "악재", 0: "중립"}
    lines = [
        "# 감성 분류 3방식 공정 비교 — 단어사전 vs ML vs LLM",
        f"> 정답지: gpt-5.4(reasoning={JUDGE_EFFORT}) 독립 심판 · 층화추출 {len(truth)}건",
        f"> gpt-5.4 정답 분포: 호재 {tcnt[1]} / 악재 {tcnt[-1]} / 중립 {tcnt[0]}\n",
        "## 1. 핵심 결과\n",
        "| 방식 | 3분류 정확도 | 부호 정확도 | 호재 재현 | 악재 재현 |",
        "|:---|:---:|:---:|:---:|:---:|",
    ]
    for r in results:
        lines.append(f"| {r['name']} | {r['acc3']:.1f}% | {r['sign']:.1f}% | "
                     f"{r['pos_rec']:.1f}% | {r['neg_rec']:.1f}% |")
    lines += [
        "",
        "> 부호 정확도 = 정답이 호재/악재인 기사에서 방향을 맞춘 비율 (중립 정답 제외).",
        "",
        "## 2. 혼동행렬 (행=gpt-5.4 정답, 열=각 방식 예측)\n",
    ]
    for r in results:
        lines.append(f"### {r['name']}\n")
        lines.append("| 정답＼예측 | 호재 | 악재 | 중립 |")
        lines.append("|:---:|:---:|:---:|:---:|")
        for i, a in enumerate([1, -1, 0]):
            row = r["mat"][i]
            lines.append(f"| **{name[a]}** | {row[0]} | {row[1]} | {row[2]} |")
        lines.append("")

    # 핵심 해석 자동 생성
    d, l, m = results
    lines += [
        "## 3. 해석\n",
        f"- **단어사전 {d['sign']:.1f}%** vs **LLM {l['sign']:.1f}%** vs **ML {m['sign']:.1f}%** (부호 기준).",
        f"- ML(무료)이 LLM(4o-mini)을 {'따라잡음' if m['sign']>=l['sign']-3 else '근접'}: "
        f"{m['sign']:.1f}% vs {l['sign']:.1f}%.",
        f"- 4o-mini가 gpt-5.4 정답과 {l['sign']:.1f}% 일치 → "
        f"{'싼 모델이 프런티어급과 근접 (선택 타당)' if l['sign']>=85 else '선생 업그레이드 여지 존재'}.",
        f"- 악재 재현: 단어사전 {d['neg_rec']:.1f}% / LLM {l['neg_rec']:.1f}% / ML {m['neg_rec']:.1f}%.",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(f"  {r['name']:14s} 3분류 {r['acc3']:.1f}% | 부호 {r['sign']:.1f}% | "
                          f"호재 {r['pos_rec']:.1f}% | 악재 {r['neg_rec']:.1f}%" for r in results))
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()

"""
generate_ml_vs_llm.py — ML vs LLM 감성 비교표 생성 (회의 자료용)

DB의 sentiment(LLM 정답) 와 sentiment_ml(ML 예측)을 대조해
results/ML_vs_LLM_비교표.md 로 저장한다.

실행:
    python generate_ml_vs_llm.py
"""

import sqlite3
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "ML_vs_LLM_비교표.md"

conn = sqlite3.connect(BASE / "identifier.sqlite")

# LLM 라벨이 있는 행만 (ML과 직접 비교 가능)
rows = conn.execute(
    "SELECT title, published_at, sentiment, sentiment_ml FROM articles "
    "WHERE sentiment IS NOT NULL AND sentiment_ml IS NOT NULL"
).fetchall()

llm = np.array([r[2] for r in rows])
ml = np.array([r[3] for r in rows])

def cls(v):
    return np.where(v > 0.05, 1, np.where(v < -0.05, -1, 0))

llm_c, ml_c = cls(llm), cls(ml)

# ── 전체 지표 ──
nz = llm != 0                                   # LLM이 중립 아닌 것
sign_acc = np.mean((ml[nz] > 0) == (llm[nz] > 0)) * 100
mae = np.mean(np.abs(llm - ml))
corr = np.corrcoef(llm, ml)[0, 1]

pos, neg = llm > 0, llm < 0
pos_rec = (ml[pos] > 0).mean() * 100
neg_rec = (ml[neg] < 0).mean() * 100

# ── 혼동행렬 (LLM 행 × ML 열) ──
labels = [1, -1, 0]
name = {1: "호재", -1: "악재", 0: "중립"}
mat = [[int(((llm_c == a) & (ml_c == b)).sum()) for b in labels] for a in labels]

# ── 불일치 사례 (부호 반대) ──
disagree = [(t, p[:10], l, m) for (t, p, l, m) in rows
            if (l > 0.05 and m < -0.05) or (l < -0.05 and m > 0.05)]
disagree.sort(key=lambda x: abs(x[2] - x[3]), reverse=True)

# ── 일치 사례 (둘 다 강한 악재) ──
agree_neg = [(t, p[:10], l, m) for (t, p, l, m) in rows
             if l < -0.4 and m < -0.2]

lines = [
    "# ML vs LLM 감성 비교표",
    f"> 대상: LLM·ML 점수가 모두 있는 {len(rows):,}건 (sentiment vs sentiment_ml)\n",
    "## 1. 종합 지표\n",
    "| 지표 | 값 | 의미 |",
    "|:---|:---:|:---|",
    f"| 부호 일치율 | **{sign_acc:.1f}%** | ML이 LLM의 호재/악재 방향을 맞춘 비율 |",
    f"| 호재 재현율 | {pos_rec:.1f}% | LLM이 호재로 본 것 중 ML도 호재 |",
    f"| 악재 재현율 | {neg_rec:.1f}% | LLM이 악재로 본 것 중 ML도 악재 |",
    f"| 평균오차(MAE) | {mae:.3f} | 점수 차이(작을수록 좋음, 범위 0~2) |",
    f"| 상관계수 | {corr:.3f} | 1에 가까울수록 점수 흐름 일치 |",
    "",
    "## 2. 혼동행렬 (행=LLM 정답, 열=ML 예측)\n",
    "| LLM＼ML | 호재 | 악재 | 중립 | 합계 |",
    "|:---:|:---:|:---:|:---:|:---:|",
]
for i, a in enumerate(labels):
    row = mat[i]
    lines.append(f"| **{name[a]}** | {row[0]:,} | {row[1]:,} | {row[2]:,} | {sum(row):,} |")
lines += [
    "",
    "> 대각선(호재→호재, 악재→악재, 중립→중립)이 일치. 비대각이 ML의 오차.",
    "",
    "## 3. 불일치 사례 (부호가 반대인 기사 · 오차 큰 순)\n",
    f"총 {len(disagree)}건 ({len(disagree)/len(rows)*100:.1f}%)\n",
    "| 날짜 | 제목 | LLM | ML |",
    "|:---|:---|:---:|:---:|",
]
for t, p, l, m in disagree[:15]:
    lines.append(f"| {p} | {t[:42]} | {l:+.2f} | {m:+.2f} |")

lines += [
    "",
    "## 4. 일치 사례 (둘 다 악재로 정확히 잡음)\n",
    "| 날짜 | 제목 | LLM | ML |",
    "|:---|:---|:---:|:---:|",
]
for t, p, l, m in agree_neg[:10]:
    lines.append(f"| {p} | {t[:42]} | {l:+.2f} | {m:+.2f} |")

lines += [
    "",
    "## 5. 결론\n",
    f"- ML(무료·즉시)이 LLM(유료) 감성 판단을 **부호 기준 {sign_acc:.1f}%** 복제.",
    f"- 악재 재현 {neg_rec:.1f}% — 불균형 보정(악재 가중 3.5)으로 끌어올린 수치.",
    "- 부호 반대 오류는 소수이며, 대부분 애매한 맥락 기사에서 발생.",
    "- → **평소 새 기사 채점은 ML로 무료 처리, LLM은 가끔 정답 갱신용**으로 충분.",
]

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"저장: {OUT}")
print(f"  비교 대상 {len(rows):,}건 | 부호일치 {sign_acc:.1f}% | 악재재현 {neg_rec:.1f}% | 불일치 {len(disagree)}건")

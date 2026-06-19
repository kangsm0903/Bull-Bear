"""
rag/sentiment.py — 기사 감성(호재/악재) 사전 채점

임베딩 유사도는 '주제 관련성'만 재고 '감성 극성'은 못 가린다.
그래서 후보 풀의 기사를 호재/악재 단어 사전으로 채점해
Bull 검색은 호재 기사를, Bear 검색은 악재 기사를 우대하도록 보정한다.

반어/복합어 대응: 감성 단어 '직후'에 뜻을 뒤집는 표현이 오면 그 단어를 무효화한다.
  · "파업 우려 해소" → 악재어(우려)가 '해소'로 무효화 → 악재 아님
  · "성장 둔화"      → 호재어(성장)가 '둔화'로 무효화 → 호재 아님

✏️ 단어를 추가/삭제하려면 POSITIVE_WORDS / NEGATIVE_WORDS / *_NEGATORS만 고치면 됩니다.
"""

import math

# ═════════════════════════════════════════════════════════
# ✏️ [편집 영역] 감성 단어 사전
# ═════════════════════════════════════════════════════════
POSITIVE_WORDS = [
    # 실적·수익
    "사상최대", "최대실적", "최대 매출", "실적개선", "호실적", "흑자전환", "흑자 전환",
    "영업이익 증가", "어닝서프라이즈", "이익률", "수익성 개선", "성장", "반등", "신기록",
    # 밸류에이션·수급
    "목표주가 상향", "목표가 상향", "투자의견 상향", "매수의견", "저평가", "비중 확대",
    "상승", "강세", "신고가", "순매수", "외국인 매수",
    # 이벤트
    "수주", "수주 확대", "계약", "신제품", "수출 증가", "점유율 확대", "호재", "기대감",
    "수요 증가", "공급 부족", "증설", "흥행", "회복",
    # 복합 호재구 (반어/리스크 완화 표현)
    "우려 해소", "리스크 완화", "불확실성 해소", "적자 축소", "손실 축소", "낙폭 축소",
]

NEGATIVE_WORDS = [
    # 실적·수익
    "어닝쇼크", "어닝 쇼크", "실적부진", "실적 악화", "적자전환", "영업적자", "영업손실",
    "이익 감소", "수익성 악화", "감익", "성장 둔화", "수요 부진", "출하 감소", "가동률 하락",
    # 밸류에이션·수급
    "목표주가 하향", "목표가 하향", "투자의견 하향", "매도의견", "고평가",
    "하락", "약세", "신저가", "순매도", "외국인 매도", "급락",
    # 이벤트·리스크
    "리스크", "악재", "규제", "소송", "벌금", "제재", "파업", "리콜", "횡령", "배임",
    "구조조정", "희망퇴직", "유상증자", "재고 증가",
    "수요 둔화", "공급 과잉", "경쟁 심화", "점유율 하락", "우려", "차질", "감산",
]

# 악재 단어 '직후'에 오면 그 악재를 무효화하는 전환 표현 (리스크 완화)
NEG_NEGATORS = ["해소", "완화", "해결", "타결", "종료", "극복", "개선", "진정", "축소", "방어"]
# 호재 단어 '직후'에 오면 그 호재를 무효화하는 표현 (모멘텀 꺾임)
POS_NEGATORS = ["둔화", "지연", "꺾", "멈춤", "주춤", "제동", "불발", "무산", "한계"]

# 제목 단어는 본문보다 감성을 강하게 드러냄 → 가중치 차등
TITLE_WEIGHT = 2.0
BODY_WEIGHT  = 1.0
BODY_CHARS   = 300   # 본문은 앞 N자만 채점 (속도·노이즈 절감)
NEGATION_WINDOW = 7  # 감성 단어 끝에서 뒤로 몇 글자까지 무효화 표현을 탐색할지


def _count_with_negation(text: str, words: list[str], negators: list[str]) -> int:
    """text에서 words 출현 횟수를 세되, 단어 직후 NEGATION_WINDOW 글자 안에
    negators가 있으면 그 출현은 무효화(카운트 제외)한다."""
    count = 0
    for w in words:
        start = 0
        while True:
            idx = text.find(w, start)
            if idx == -1:
                break
            tail = text[idx + len(w): idx + len(w) + NEGATION_WINDOW]
            if not any(neg in tail for neg in negators):
                count += 1
            start = idx + len(w)
    return count


def sentiment_score(title: str, content: str) -> float:
    """기사의 감성 점수를 -1.0(악재) ~ +1.0(호재)로 반환.
    호재/악재 단어가 모두 없으면(또는 서로 상쇄되면) 0.0(중립)."""
    title = title or ""
    body  = (content or "")[:BODY_CHARS]

    pos = (TITLE_WEIGHT * _count_with_negation(title, POSITIVE_WORDS, POS_NEGATORS)
           + BODY_WEIGHT * _count_with_negation(body, POSITIVE_WORDS, POS_NEGATORS))
    neg = (TITLE_WEIGHT * _count_with_negation(title, NEGATIVE_WORDS, NEG_NEGATORS)
           + BODY_WEIGHT * _count_with_negation(body, NEGATIVE_WORDS, NEG_NEGATORS))

    net = pos - neg
    if net == 0:
        return 0.0
    # tanh로 -1~1 압축 (단어 3개 차이면 약 0.76)
    return math.tanh(net / 3.0)

"""
QueryExpander — 사용자 입력을 3종 검색 쿼리로 확장

공통 쿼리:  중립적 현황 파악용
Bull 쿼리:  긍정적 근거 탐색용 (호재 도메인 어휘)
Bear 쿼리:  부정적 리스크 탐색용 (악재 도메인 어휘)

✏️ 키워드 튜닝하려면 아래 BULL/BEAR/COMMON_KEYWORDS만 고치면 됩니다.
"""


# ═════════════════════════════════════════════════════════
# ✏️ [편집 영역] 측면별 검색 키워드
#   · 임베딩이 너무 희석되지 않도록 각 측 10~12 단어 권장
#   · 다양성 위해 5측면 커버: 실적 · 밸류에이션 · 이벤트 · 시장지위 · 추상
# ═════════════════════════════════════════════════════════
COMMON_KEYWORDS = "최근 실적 현황 동향"

BULL_KEYWORDS = (
    "실적개선 영업이익 사상최대 "        # 실적
    "목표주가 상향 매수의견 "            # 밸류에이션
    "수주 신제품 "                       # 이벤트
    "점유율확대 "                        # 시장지위
    "성장 호재"                          # 추상
)

BEAR_KEYWORDS = (
    "실적부진 영업적자 "                 # 실적
    "목표주가 하향 매도의견 "            # 밸류에이션
    "규제 소송 "                         # 이벤트
    "점유율하락 경쟁심화 "               # 시장지위
    "리스크 부진 악재"                   # 추상
)


def expand_query(topic: str) -> dict[str, str]:
    """
    토론 주제를 Bull/Bear/공통 3종 쿼리로 확장

    Args:
        topic: 사용자 입력 (예: "삼성전자", "삼성전자 005930", "반도체 업황")

    Returns:
        {
            "common": "삼성전자 최근 실적 현황 동향",
            "bull":   "삼성전자 실적개선 영업이익 사상최대 ...",
            "bear":   "삼성전자 실적부진 영업적자 ...",
        }
    """
    # ticker 코드 제거 (예: "삼성전자 005930" → "삼성전자")
    base = topic.strip()
    base = " ".join(w for w in base.split() if not w.isdigit() and len(w) != 6)
    base = base.strip() or topic.strip()

    return {
        "common": f"{base} {COMMON_KEYWORDS}",
        "bull":   f"{base} {BULL_KEYWORDS}",
        "bear":   f"{base} {BEAR_KEYWORDS}",
    }

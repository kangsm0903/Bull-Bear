"""
QueryExpander — 사용자 입력을 3종 검색 쿼리로 확장

공통 쿼리:  중립적 현황 파악용
Bull 쿼리:  긍정적 근거 탐색용
Bear 쿼리:  부정적 리스크 탐색용
"""


def expand_query(topic: str) -> dict[str, str]:
    """
    토론 주제를 Bull/Bear/공통 3종 쿼리로 확장

    Args:
        topic: 사용자 입력 (예: "삼성전자", "삼성전자 005930", "반도체 업황")

    Returns:
        {
            "common": "삼성전자 최근 실적 현황 동향",
            "bull":   "삼성전자 성장 호재 기회 상승",
            "bear":   "삼성전자 리스크 악재 하락 우려",
        }

    Example:
        >>> expand_query("삼성전자")
        {'common': '삼성전자 최근 실적 현황 동향',
         'bull':   '삼성전자 성장 호재 기회 상승',
         'bear':   '삼성전자 리스크 악재 하락 우려'}
    """
    # ticker 코드 제거 (예: "삼성전자 005930" → "삼성전자")
    base = topic.strip()
    base = " ".join(w for w in base.split() if not w.isdigit() and len(w) != 6)
    base = base.strip() or topic.strip()

    return {
        "common": f"{base} 최근 실적 현황 동향",
        "bull":   f"{base} 성장 호재 기회 상승 긍정",
        "bear":   f"{base} 리스크 악재 하락 우려 부정",
    }

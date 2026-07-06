package com.bullbear.backend.debate.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * 서버 -> 사용자로 나가는 데이터
 */
public record DebateResponse(
        List<Message> messages, // 토론 발언 여러 개 (리스트 형태)
        List<Article> articles, // 토론에 사용된 기사 여러 개 (리스트 형태)

        // @JsonProperty는 JSON으로 나갈 땐 괄호 안의 이름으로 나가도록 설정
        // React랑 Java랑 default naming이 다르기 떄문
        @JsonProperty("bull_score") double bullScore,
        @JsonProperty("bear_score") double bearScore,
        Moderator moderator // 사회자 평가 한 덩어리
) {

    /** 토론 발언 하나.
     * id: 발언 고유 번호
     * agent: 어느 에이전트가 말했는가
     * kind: 발언의 종류 - argue/rebut/conclude
     * round: 몇 번째 라운드인지
     * message: 실제 말한 내용
     * timestamp: 말한 시각
     *
     * */
    public record Message(
            String id,
            String agent,
            String kind,
            Integer round,
            String message,
            String timestamp
    ) {}

    /** 토론에 인용된 기사.
     * source: 기사 출처 (어느 언론사)
     * date: 기사 날짜
     * url: 기사 링크 주소
     * referenceBy: 이 기사를 누가 인용했나 - bull / bear / both
     * */
    public record Article(
            String id,
            String title,
            String source,
            String date,
            String url,
            String referencedBy
    ) {}

    /** 사회자 최종 평가.
     * bullSummary: 황소 주장 요약
     * bearSummary: 곰 주장 요약
     * conclusion: 사회자의 결론
     * verdict: 최종 판정 - 매수 적극 / 분할매수 / 관망 / 매도 고려
     * dataBalance: 근거 균형 (황소, 곰 어느 쪽 자료가 더 많았는가)
     * */
    public record Moderator(
            @JsonProperty("bull_summary") String bullSummary,
            @JsonProperty("bear_summary") String bearSummary,
            String conclusion,
            String verdict,
            @JsonProperty("data_balance") String dataBalance
    ) {}
}

package com.bullbear.backend.debate.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * POST /api/debate 응답 바디.
 * 프론트 DebateChat.tsx의 DebateData 인터페이스와 필드명이 정확히 일치해야 한다.
 * JSON 키가 snake_case인 필드는 @JsonProperty로 매핑 (Java 필드는 camelCase 관례 유지).
 */
public record DebateResponse(
        List<Message> messages,
        List<Article> articles,
        @JsonProperty("bull_score") double bullScore,
        @JsonProperty("bear_score") double bearScore,
        Moderator moderator
) {

    /** 토론 발언 하나. agent: "bull"|"bear", kind: "argue"|"rebut"|"conclude" */
    public record Message(
            String id,
            String agent,
            String kind,
            Integer round,
            String message,
            String timestamp
    ) {}

    /** 토론에 인용된 기사. referencedBy: "bull"|"bear"|"both" (프론트가 camelCase로 기대) */
    public record Article(
            String id,
            String title,
            String source,
            String date,
            String url,
            String referencedBy
    ) {}

    /** 사회자 최종 평가. verdict는 프론트 VERDICT_LABEL 키 중 하나: 매수 적극|분할 매수|관망|매도 고려 */
    public record Moderator(
            @JsonProperty("bull_summary") String bullSummary,
            @JsonProperty("bear_summary") String bearSummary,
            String conclusion,
            String verdict,
            @JsonProperty("data_balance") String dataBalance
    ) {}
}

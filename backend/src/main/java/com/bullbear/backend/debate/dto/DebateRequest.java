package com.bullbear.backend.debate.dto;

/**
 * 사용자 -> 서버로 들어오는 데이터
 */
public record DebateRequest(String topic, Survey survey) {

    /**
     * depth: 설명 깊이 - 쉽고 간단 / 균형 / 심층 정밀
     * horizon: 희망투자기간 - 단기 / 중기 / 장기
     * */
    public record Survey(String depth, String horizon) {}
}

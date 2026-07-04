package com.bullbear.backend.debate.dto;

/**
 * POST /api/debate 요청 바디.
 * 프론트: fetch('/api/debate', { body: JSON.stringify({ topic, survey }) })
 *
 * record: 불변 데이터 클래스. 필드·생성자·getter·equals/hashCode를 자동 생성.
 * DTO처럼 "값을 담기만 하는" 클래스에 딱 맞는 Java 16+ 문법.
 */
public record DebateRequest(String topic, Survey survey) {

    /** 프론트 InputScreen의 설문. 모든 항목이 선택 사항이라 null일 수 있음. */
    public record Survey(String level, String terminology, String depth, String horizon) {}
}

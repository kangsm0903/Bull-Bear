package com.bullbear.backend.debate;

import com.bullbear.backend.debate.dto.DebateRequest;
import com.bullbear.backend.debate.dto.DebateResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;

/**
 * 토론 생성 담당(요리사). 실제 토론은 Python AI 서비스(:8001)에 맡기고,
 * 그 결과를 받아온다. Controller는 이 서비스에 일을 시키기만 한다.
 */
@Service   // 해당 클래스는 비즈니스 로직 담당 부품(Bean)이다
public class DebateService {

    // RestClient: Spring -> Python 서버로 요청 보낼때 Spring을 client로 만들기 위한 도구
    private final RestClient restClient;

    /**
     * - RestClient.Builder : 스프링 부트가 미리 준비해둔 HTTP 클라이언트 조립기(Bean)
     * - @Value("${ai.service.url}") : application.properties의 ai.service.url 값을 꺼내 넣어줌
     */
    public DebateService(RestClient.Builder builder,
                         @Value("${ai.service.url}") String aiServiceUrl) {
        // HTTP 통신을 구판(HTTP/1.1)으로 고정. (기본값은 HTTP/2를 시도해서 uvicorn과 대화가 꼬이고 본문이 유실됨 → 422 발생하던 문제 해결)
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();

        // 조립기에 Python 기본 주소 + HTTP/1.1 도구를 박아 RestClient 하나를 완성해둔다.
        this.restClient = builder
                .baseUrl(aiServiceUrl)
                .requestFactory(new JdkClientHttpRequestFactory(httpClient))
                .build();
    }

    /** 주문서를 Python 주방에 그대로 넘기고, 완성된 토론 결과를 받아 돌려준다. */
    public DebateResponse generateDebate(DebateRequest request) {
        return restClient.post()                            // POST 요청을
                .uri("/debate")                         // (기본주소)+/debate = http://localhost:8001/debate 로
                .contentType(MediaType.APPLICATION_JSON)    // "이 본문은 JSON입니다" 봉투 표시
                .body(request)                              // 주문서(request)를 JSON으로 바꿔 실어 보내고
                    .retrieve()                             // 응답을 받을때까지 대기
                .body(DebateResponse.class);                // JSON을 DebateResponse 상자로 되돌린다
    }
}

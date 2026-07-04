package com.bullbear.backend.debate;

import com.bullbear.backend.debate.dto.DebateRequest;
import com.bullbear.backend.debate.dto.DebateResponse;
import com.bullbear.backend.debate.dto.DebateResponse.Article;
import com.bullbear.backend.debate.dto.DebateResponse.Message;
import com.bullbear.backend.debate.dto.DebateResponse.Moderator;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 토론 API 진입점.
 *
 * @RestController = @Controller + @ResponseBody.
 *   반환 객체를 뷰(HTML)가 아니라 JSON으로 직렬화해 응답한다.
 * @RequestBody: HTTP 요청 바디의 JSON을 DebateRequest 객체로 역직렬화(Jackson).
 *
 * [Week 1] 지금은 하드코딩 목업 응답. UI ↔ Spring 연결 검증이 목적.
 * [Week 2] 이 안을 Python AI 서비스(FastAPI :8001) 호출로 교체 예정.
 */
@RestController
@RequestMapping("/api")
public class DebateController {

    @PostMapping("/debate")
    public DebateResponse debate(@RequestBody DebateRequest request) {
        String topic = request.topic();
        String now = LocalDateTime.now().toString();

        List<Message> messages = List.of(
                new Message("m1", "bull", "argue", 1,
                        "[목업] " + topic + " — 실적 개선 흐름이 뚜렷해 상승 여력이 충분합니다.", now),
                new Message("m2", "bear", "argue", 1,
                        "[목업] " + topic + " — 밸류에이션 부담과 거시 리스크가 과소평가돼 있습니다.", now),
                new Message("m3", "bull", "conclude", 2,
                        "[목업] 결론적으로 중장기 관점의 분할 매수가 유효합니다.", now),
                new Message("m4", "bear", "conclude", 2,
                        "[목업] 결론적으로 현시점 진입은 성급하며 관망을 권합니다.", now)
        );

        List<Article> articles = List.of(
                new Article("a1", "[목업] " + topic + " 2분기 실적 시장 기대치 상회",
                        "테스트뉴스", "2026-07-04", "https://example.com/1", "bull"),
                new Article("a2", "[목업] 반도체 업황 둔화 우려 확산",
                        "테스트뉴스", "2026-07-03", "https://example.com/2", "bear")
        );

        Moderator moderator = new Moderator(
                "[목업] 실적 개선과 수급 유입을 근거로 상승을 주장.",
                "[목업] 밸류에이션 부담과 거시 불확실성을 근거로 하락을 주장.",
                "[목업] 양측 근거가 팽팽하므로 추가 확인이 필요한 구간.",
                "관망",
                "bull 1건 / bear 1건 — 균형"
        );

        return new DebateResponse(messages, articles, 6.5, 5.5, moderator);
    }
}

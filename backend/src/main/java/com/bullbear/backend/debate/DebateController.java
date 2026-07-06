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
 * 주문 받는 창구 직원
 */
@RestController             // 화면(HTML)말고 데이터(JSON)을 주는 창구라는 표시
@RequestMapping("/api")     // 내 주소는 /api로 시작

public class DebateController {

    @PostMapping("/debate") // /api/debate 주소로 오는 주문을 받겠다
    public DebateResponse debate(@RequestBody DebateRequest request) {
        // 유저가 보낸 JSON을 DebateRequest에 담아서 request란 이름으로 나에게 전달
        // @RequestBody: header-json으로 겉면의 정보, body-진짜 알맹이 데이터로 body의 정보를 꺼내서 담으라는 뜻
        // @RequestBody 자체는 명령이 적힌 스티커라고 보면 됨 | DebateRequest = 상자 설계도 | request = 상자 별명
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

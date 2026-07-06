package com.bullbear.backend.debate;

import com.bullbear.backend.debate.dto.DebateRequest;
import com.bullbear.backend.debate.dto.DebateResponse;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 웹 요청과 응답만 담당
 * 비즈니스 로직은 DebateService로 넘김
 */
@RestController             // 화면(HTML)말고 데이터(JSON)을 주는 창구라는 표시
@RequestMapping("/api")     // 내 주소는 /api로 시작
public class DebateController {

    // 요리사(Service)에 대한 의존. 직접 new 하지 않고 스프링이 주입해준다(DI).
    private final DebateService debateService;

    // 생성자 주입: 스프링이 DebateService Bean을 찾아 여기에 넣어준다.
    public DebateController(DebateService debateService) {
        this.debateService = debateService;
    }

    @PostMapping("/debate") // /api/debate 주소로 오는 주문을 받겠다
    public DebateResponse debate(@RequestBody DebateRequest request) {
        // 요리는 서비스에 맡기고, 그 결과를 그대로 돌려준다.
        return debateService.generateDebate(request);
    }
}

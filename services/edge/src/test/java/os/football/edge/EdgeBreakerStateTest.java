package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The breaker door reports what the route's protection is actually doing.
 *
 * <p>The core here is a refused port, so every routed call fails and the fallback answers 503. The door is
 * read before the first call (nothing exists yet — `present=false`), after one failure (one buffered call,
 * one failure, failure rate 100), and the thresholds are compared with the values the configuration
 * declares. That last comparison is the one that catches a config block which is present but not applied.
 *
 * <p>The order is declared because the two readings describe one breaker's life: before its first call,
 * and after one failure. Sharing a context and reading in the other order would contradict itself.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class EdgeBreakerStateTest {

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void deadCore(DynamicPropertyRegistry registry) {
        registry.add("apc.core-uri", () -> "http://127.0.0.1:1");
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
    }

    @Test
    @Order(1)
    void the_door_reports_a_breaker_that_has_not_been_used_yet() {
        Map<?, ?> report = readReport();
        assertThat(report.get("present")).isEqualTo(false);
        assertThat(report.get("state")).isEqualTo("NOT_CREATED");
    }

    @Test
    @Order(2)
    void a_failed_call_is_visible_with_the_thresholds_in_force() {
        // One failed routed call. The fallback answers; the breaker records the failure.
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isEqualTo(503);

        Map<?, ?> report = readReport();
        assertThat(report.get("present")).isEqualTo(true);
        assertThat(report.get("state")).isEqualTo("CLOSED");
        assertThat(((Number) report.get("bufferedCalls")).intValue()).isEqualTo(1);
        assertThat(((Number) report.get("failedCalls")).intValue()).isEqualTo(1);
        // Not a percentage yet: the rolling window needs five calls before it computes one. This is also
        // why the config sets minimum-number-of-calls to 5 — the stock 100 inside a 10-call window would
        // make the breaker decoration that can never open.
        assertThat(((Number) report.get("failureRate")).floatValue()).isEqualTo(-1.0f);
        assertThat(((Number) report.get("slidingWindowSize")).intValue()).isEqualTo(10);
        assertThat(((Number) report.get("failureRateThreshold")).floatValue()).isEqualTo(50.0f);
        assertThat(((Number) report.get("minimumNumberOfCalls")).intValue()).isEqualTo(5);
        assertThat(((Number) report.get("permittedCallsInHalfOpenState")).intValue()).isEqualTo(3);
    }

    @Test
    @Order(3)
    void enough_failures_open_the_breaker_and_a_further_call_is_not_permitted() {
        // Four more failed calls, five in total: over the threshold with the window's minimum reached.
        for (int i = 0; i < 4; i++) {
            client.get()
                    .uri("http://localhost:" + edgePort + "/api/v1/health")
                    .exchange()
                    .expectStatus().isEqualTo(503);
        }

        Map<?, ?> open = readReport();
        assertThat(open.get("state")).isEqualTo("OPEN");
        assertThat(((Number) open.get("bufferedCalls")).intValue()).isEqualTo(5);
        assertThat(((Number) open.get("failedCalls")).intValue()).isEqualTo(5);
        assertThat(((Number) open.get("failureRate")).floatValue()).isEqualTo(100.0f);

        // The next call never reaches the core: the breaker refuses it and the fallback answers.
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isEqualTo(503);

        Map<?, ?> refused = readReport();
        assertThat(((Number) refused.get("notPermittedCalls")).longValue()).isEqualTo(1L);
    }

    private Map<?, ?> readReport() {
        Map<?, ?> report = client.get()
                .uri("http://localhost:" + edgePort + "/edge/breaker")
                .exchange()
                .expectStatus().isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
        assertThat(report).isNotNull();
        return report;
    }
}

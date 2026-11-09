package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The edge when the core is not there: a refusal a client can act on, carrying the trace id.
 *
 * <p>The route points at a port nothing listens on, which is the same failure a crashed core produces —
 * a connection refused, not a slow answer — so the circuit breaker's fallback runs on the first call
 * rather than after a window of failures. The assertion is not "something failed": it is that the body
 * has the product's refusal shape and that the id in the body is the id in the header.
 */
@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
            "apc.core-uri=http://127.0.0.1:1",
            "eureka.client.enabled=false",
            "spring.cloud.config.enabled=false"
        })
class EdgeFallbackTest {

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @Test
    void a_dead_core_answers_the_products_refusal_shape_with_the_trace_id() {
        String supplied = "fallback-987";
        Map<?, ?> body = client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .header(TraceIdFilter.TRACE_HEADER, supplied)
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectHeader().valueEquals(TraceIdFilter.TRACE_HEADER, supplied)
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(body).isNotNull();
        assertThat(body.get("code")).isEqualTo("core_unavailable");
        assertThat(body.get("trace_id")).isEqualTo(supplied);
        assertThat(body.get("retryable")).isEqualTo(true);
        assertThat(String.valueOf(body.get("message"))).contains("edge").doesNotContain("Traceback");
    }
}

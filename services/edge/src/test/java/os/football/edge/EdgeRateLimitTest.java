package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The ceiling: a burst is served, the request after it is refused in the product's shape, and the bucket
 * refills by elapsed time rather than by a timer.
 *
 * <p>The policy is set small (burst 2, 20 per second) so the test can spend and replenish it within a
 * second. Both ends are read: the two accepted requests reach the stub core, and the refused one does not
 * — the stub counts its calls, so "the request was not forwarded" is measured, not assumed.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeRateLimitTest {

    private static HttpServer core;
    private static int coreCalls;

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void smallBucket(DynamicPropertyRegistry registry) throws IOException {
        core = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        core.createContext("/", exchange -> {
            coreCalls++;
            byte[] body = "{\"core\":true}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        core.start();
        registry.add("apc.core-uri", () -> "http://127.0.0.1:" + core.getAddress().getPort());
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
        registry.add("edge.rate-limit.burst", () -> "2");
        registry.add("edge.rate-limit.requests-per-second", () -> "20");
    }

    @AfterAll
    static void stopCore() {
        if (core != null) {
            core.stop(0);
        }
    }

    @Test
    void the_burst_is_served_then_the_next_request_is_refused_and_the_bucket_refills() throws InterruptedException {
        for (int i = 0; i < 2; i++) {
            client.get()
                    .uri("http://localhost:" + edgePort + "/api/v1/health")
                    .exchange()
                    .expectStatus().isOk()
                    .expectHeader().valueEquals(RateLimitFilter.LIMIT_HEADER, "2");
        }
        assertThat(coreCalls).isEqualTo(2);

        Map<?, ?> refusal = client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isEqualTo(429)
                .expectHeader().valueEquals(RateLimitFilter.REMAINING_HEADER, "0")
                .expectHeader().exists(HttpHeaders.RETRY_AFTER)
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(refusal).isNotNull();
        assertThat(refusal.get("code")).isEqualTo("rate_limited");
        assertThat(refusal.get("retryable")).isEqualTo(true);
        assertThat(String.valueOf(refusal.get("trace_id"))).isNotBlank();
        assertThat(coreCalls).as("a refused request must not reach the core").isEqualTo(2);

        // 20 tokens per second: 300 ms buys six, so the next request fits without waiting for a full second.
        Thread.sleep(300);
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isOk();
        assertThat(coreCalls).isEqualTo(3);
    }

    @Test
    void the_policy_is_read_from_the_running_filter() {
        Map<?, ?> limits = client.get()
                .uri("http://localhost:" + edgePort + "/edge/limits")
                .exchange()
                .expectStatus().isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(limits).isNotNull();
        assertThat(limits.get("enabled")).isEqualTo(true);
        assertThat(((Number) limits.get("burst")).intValue()).isEqualTo(2);
        assertThat(((Number) limits.get("requestsPerSecond")).doubleValue()).isEqualTo(20.0);
    }
}

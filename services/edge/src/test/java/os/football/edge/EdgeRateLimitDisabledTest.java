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
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The opt-out: with `edge.rate-limit.enabled=false` a caller can exceed the burst and nothing is refused.
 *
 * <p>Without this case the enabled flag would only be a branch nobody reads back — and an operator who
 * turns the limit off to diagnose something would have no test saying that it actually turns off.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeRateLimitDisabledTest {

    private static HttpServer core;

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void disabledLimit(DynamicPropertyRegistry registry) throws IOException {
        core = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        core.createContext("/", exchange -> {
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
        registry.add("edge.rate-limit.enabled", () -> "false");
        registry.add("edge.rate-limit.burst", () -> "1");
        registry.add("edge.rate-limit.requests-per-second", () -> "0.1");
    }

    @AfterAll
    static void stopCore() {
        if (core != null) {
            core.stop(0);
        }
    }

    @Test
    void a_disabled_limit_refuses_nothing_and_says_so() {
        for (int i = 0; i < 4; i++) {
            client.get()
                    .uri("http://localhost:" + edgePort + "/api/v1/health")
                    .exchange()
                    .expectStatus().isOk();
        }

        Map<?, ?> limits = client.get()
                .uri("http://localhost:" + edgePort + "/edge/limits")
                .exchange()
                .expectStatus().isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(limits).isNotNull();
        assertThat(limits.get("enabled")).isEqualTo(false);
        assertThat(((Number) limits.get("burst")).intValue()).isEqualTo(1);
    }
}

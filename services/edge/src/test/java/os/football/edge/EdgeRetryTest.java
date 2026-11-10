package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * A transient failure heals itself at the door, and the retry does not multiply the breaker's count.
 *
 * <p>The stub core records how many times it was actually called, so these cases measure the attempts,
 * not the gateway's description of them. CircuitBreaker is the outer route filter and Retry the inner
 * one: one caller request is one breaker observation even when three attempts went downstream.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeRetryTest {

    private static HttpServer core;
    private static final AtomicInteger CALLS = new AtomicInteger();
    private static volatile int failFirst;
    private static volatile int failureStatus;
    private static volatile boolean alwaysFail;

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void coreAddress(DynamicPropertyRegistry registry) throws IOException {
        core = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        core.createContext("/", exchange -> {
            int attempt = CALLS.incrementAndGet();
            boolean fail = alwaysFail || attempt <= failFirst;
            int status = fail ? failureStatus : 200;
            byte[] body = ("{\"attempt\":" + attempt + ",\"status\":" + status + "}").getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        core.start();
        registry.add("apc.core-uri", () -> "http://127.0.0.1:" + core.getAddress().getPort());
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
        registry.add("edge.rate-limit.enabled", () -> "false");
    }

    @BeforeEach
    void reset() {
        CALLS.set(0);
        failFirst = 0;
        failureStatus = 503;
        alwaysFail = false;
    }

    @AfterAll
    static void stopCore() {
        if (core != null) {
            core.stop(0);
        }
    }

    @Test
    void a_transient_503_heals_on_the_third_attempt() {
        failFirst = 2;
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isOk();

        assertThat(CALLS.get()).isEqualTo(3);
    }

    @Test
    void a_status_the_policy_did_not_name_is_not_retried() {
        alwaysFail = true;
        failureStatus = 500;
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isEqualTo(500);

        assertThat(CALLS.get()).isEqualTo(1);
    }

    @Test
    void a_non_idempotent_method_is_never_retried() {
        alwaysFail = true;
        client.post()
                .uri("http://localhost:" + edgePort + "/api/v1/jobs")
                .exchange()
                .expectStatus().isEqualTo(503);

        assertThat(CALLS.get()).isEqualTo(1);
    }

    @Test
    void an_exhausted_get_is_attempted_three_times_and_the_last_503_reaches_the_caller() {
        alwaysFail = true;
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isEqualTo(503);

        assertThat(CALLS.get()).isEqualTo(3);
    }
}

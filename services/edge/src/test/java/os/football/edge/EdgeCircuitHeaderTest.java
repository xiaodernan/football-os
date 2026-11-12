package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The door says how it handled the request, in one header, without a dashboard.
 *
 * <p>The stub core answers, so the breaker records a success and stays CLOSED; the header must therefore
 * read {@code coreBreaker=CLOSED;outcome=pass}. The test parses the value into fields rather than comparing
 * the whole string, because the point is that a client can read a field, not that this build printed one
 * particular sentence. {@link EdgeFallbackTest} covers the other half — a dead core flips the outcome to
 * {@code fallback} while the breaker is still CLOSED — and the pair is what makes the header honest.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeCircuitHeaderTest {

    private static HttpServer core;

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void liveCore(DynamicPropertyRegistry registry) throws IOException {
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
    }

    @AfterAll
    static void stopCore() {
        if (core != null) {
            core.stop(0);
        }
    }

    @Test
    void a_routed_request_reports_the_breaker_state_and_a_pass_outcome() {
        String header = client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isOk()
                .expectHeader().exists(CircuitTraceFilter.HEADER)
                .returnResult(String.class)
                .getResponseHeaders()
                .getFirst(CircuitTraceFilter.HEADER);

        assertThat(fields(header))
                .containsEntry("coreBreaker", "CLOSED")
                .containsEntry("outcome", CircuitTraceFilter.OUTCOME_PASS);
    }

    @Test
    void the_header_is_two_key_value_fields_a_client_can_parse() {
        String header = client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isOk()
                .returnResult(String.class)
                .getResponseHeaders()
                .getFirst(CircuitTraceFilter.HEADER);

        // No spaces around the separators: a header a log pipeline splits on ';' and '=' must not need
        // trimming to produce the right key, and whitespace in a machine field is a bug waiting to bite.
        assertThat(header).doesNotContain(" ").contains("=").contains(";");
        assertThat(fields(header)).hasSize(2);
    }

    private static Map<String, String> fields(String header) {
        assertThat(header).isNotNull();
        return Arrays.stream(header.split(";"))
                .map(part -> part.split("=", 2))
                .filter(pair -> pair.length == 2)
                .collect(Collectors.toMap(pair -> pair[0], pair -> pair[1]));
    }
}

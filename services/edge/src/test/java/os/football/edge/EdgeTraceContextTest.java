package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The Java hop and the Python hop name one trace.
 *
 * <p>A real JDK HTTP server stands in for the core and records the headers it actually received; the
 * assertions read those headers, not the gateway's account of itself. The three cases are the three
 * rules the filter states: mint when absent, preserve a valid caller, and replace an invalid one.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeTraceContextTest {

    private static final String VALID = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01";
    private static final String STATE = "vendor=value";

    private static HttpServer core;
    private static String lastParent;
    private static String lastState;
    private static String lastCorrelation;

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void coreAddress(DynamicPropertyRegistry registry) throws IOException {
        core = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        core.createContext("/", exchange -> {
            lastParent = exchange.getRequestHeaders().getFirst(W3cTraceContextFilter.TRACE_PARENT);
            lastState = exchange.getRequestHeaders().getFirst(W3cTraceContextFilter.TRACE_STATE);
            lastCorrelation = exchange.getRequestHeaders().getFirst(TraceIdFilter.TRACE_HEADER);
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
    void a_request_without_a_parent_reaches_the_core_with_a_valid_one_and_the_caller_reads_it_back() {
        String echoed = client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isOk()
                .expectHeader().exists(W3cTraceContextFilter.TRACE_PARENT)
                .returnResult(String.class)
                .getResponseHeaders()
                .getFirst(W3cTraceContextFilter.TRACE_PARENT);

        assertThat(W3cTraceContextFilter.isValid(lastParent)).isTrue();
        assertThat(lastParent).isEqualTo(echoed);
        assertThat(lastCorrelation).isNotBlank();
        assertThat(lastParent).contains("-" + UUID.fromString(lastCorrelation).toString().replace("-", "") + "-");
    }

    @Test
    void a_valid_caller_parent_and_state_are_carried_through_byte_for_byte() {
        String echoed = client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/world/status")
                .header(W3cTraceContextFilter.TRACE_PARENT, VALID)
                .header(W3cTraceContextFilter.TRACE_STATE, STATE)
                .exchange()
                .expectStatus().isOk()
                .returnResult(String.class)
                .getResponseHeaders()
                .getFirst(W3cTraceContextFilter.TRACE_PARENT);

        assertThat(lastParent).isEqualTo(VALID);
        assertThat(lastState).isEqualTo(STATE);
        assertThat(echoed).isEqualTo(VALID);
    }

    @Test
    void an_invalid_parent_and_its_state_are_replaced_not_forwarded() {
        String echoed = client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/world/status")
                .header(W3cTraceContextFilter.TRACE_PARENT, "garbage")
                .header(W3cTraceContextFilter.TRACE_STATE, STATE)
                .exchange()
                .expectStatus().isOk()
                .returnResult(String.class)
                .getResponseHeaders()
                .getFirst(W3cTraceContextFilter.TRACE_PARENT);

        assertThat(W3cTraceContextFilter.isValid(lastParent)).isTrue();
        assertThat(lastParent).isNotEqualTo("garbage");
        assertThat(lastState).isNull();
        assertThat(echoed).isEqualTo(lastParent);
    }
}

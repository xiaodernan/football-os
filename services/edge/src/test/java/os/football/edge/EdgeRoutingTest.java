package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
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
 * The edge's contract, measured through a real HTTP server standing in for the core.
 *
 * <p>Three claims, and each one is read from a response rather than from the configuration: a request
 * under the routed prefix arrives at the core with the path it had, an id the caller did not supply is
 * minted and echoed, and an id the caller did supply is the one that comes back. The stub records what it
 * received in static fields, so the test can compare the two ends of the hop instead of trusting the
 * gateway's own account of itself.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeRoutingTest {

    private static HttpServer core;
    private static String lastPath;
    private static String lastTrace;

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void coreAddress(DynamicPropertyRegistry registry) throws IOException {
        core = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        core.createContext("/", exchange -> {
            lastPath = exchange.getRequestURI().toString();
            lastTrace = exchange.getRequestHeaders().getFirst(TraceIdFilter.TRACE_HEADER);
            byte[] body = ("{\"core\":true,\"path\":\"" + lastPath + "\"}").getBytes(StandardCharsets.UTF_8);
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
    void a_routed_request_reaches_the_core_with_its_path_and_mints_a_trace_id() {
        Map<?, ?> body = client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .exchange()
                .expectStatus().isOk()
                .expectHeader().exists(TraceIdFilter.TRACE_HEADER)
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(lastPath).isEqualTo("/api/v1/health");
        assertThat(body).isNotNull();
        assertThat(body.get("core")).isEqualTo(true);
        assertThat(lastTrace).isNotBlank();
        assertThat(lastTrace).isEqualTo(lastTrace.trim());
    }

    @Test
    void a_trace_id_the_caller_supplied_is_the_one_both_ends_see() {
        String supplied = "walk-1234";
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/world/competitions")
                .header(TraceIdFilter.TRACE_HEADER, supplied)
                .exchange()
                .expectStatus().isOk()
                .expectHeader().valueEquals(TraceIdFilter.TRACE_HEADER, supplied);

        assertThat(lastTrace).isEqualTo(supplied);
        assertThat(lastPath).isEqualTo("/api/v1/world/competitions");
    }

    @Test
    void the_route_table_is_what_the_gateway_resolved() {
        List<?> routes = client.get()
                .uri("http://localhost:" + edgePort + "/edge/routes")
                .exchange()
                .expectStatus().isOk()
                .expectBody(List.class)
                .returnResult()
                .getResponseBody();

        assertThat(routes).isNotNull().hasSize(1);
        Map<?, ?> route = (Map<?, ?>) routes.getFirst();
        assertThat(route.get("id")).isEqualTo("core-api");
        assertThat(String.valueOf(route.get("uri"))).startsWith("http://127.0.0.1:");
        assertThat((List<?>) route.get("predicates")).anyMatch(entry -> entry.toString().contains("/api/v1/**"));
        assertThat((List<?>) route.get("filters")).anyMatch(entry -> entry.toString().startsWith("CircuitBreaker="));
    }
}

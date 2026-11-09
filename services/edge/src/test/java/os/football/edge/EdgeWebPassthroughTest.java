package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
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
 * One door for the whole product: the API and the shell are reached through the same port.
 *
 * <p>Two stubs stand in for the two processes. The core answers `/api/v1/**`; the web shell answers
 * everything else, including the asset paths the Next.js runtime asks for. The test proves the split by
 * making a request to each and reading which stub was called with which path — a route table that
 * published a catch-all but still sent `/` to the core would fail here while `/edge/routes` looked right.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeWebPassthroughTest {

    private static HttpServer core;
    private static HttpServer web;
    private static final AtomicInteger coreCalls = new AtomicInteger();
    private static final AtomicInteger webCalls = new AtomicInteger();

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void twoStubs(DynamicPropertyRegistry registry) throws IOException {
        core = stub("core", coreCalls);
        web = stub("web", webCalls);
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
        registry.add("apc.core-uri", () -> "http://127.0.0.1:" + core.getAddress().getPort());
        registry.add("apc.web-uri", () -> "http://127.0.0.1:" + web.getAddress().getPort());
    }

    @BeforeEach
    void resetCounters() {
        coreCalls.set(0);
        webCalls.set(0);
    }

    private static HttpServer stub(String name, AtomicInteger calls) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            calls.incrementAndGet();
            String path = exchange.getRequestURI().toString();
            byte[] body = ("{\"" + name + "\":true,\"path\":\"" + path + "\"}").getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        return server;
    }

    @AfterAll
    static void stopStubs() {
        if (core != null) {
            core.stop(0);
        }
        if (web != null) {
            web.stop(0);
        }
    }

    @Test
    void the_shell_is_served_through_the_same_door_and_its_paths_survive() {
        Map<?, ?> root = get("/");
        assertThat(root.get("web")).isEqualTo(true);
        assertThat(root.get("path")).isEqualTo("/");
        assertThat(webCalls.get()).isEqualTo(1);
        assertThat(coreCalls.get()).isZero();

        Map<?, ?> asset = get("/_next/static/chunks/app.js");
        assertThat(asset.get("web")).isEqualTo(true);
        assertThat(asset.get("path")).isEqualTo("/_next/static/chunks/app.js");
        assertThat(webCalls.get()).isEqualTo(2);
        assertThat(coreCalls.get()).isZero();
    }

    @Test
    void the_api_door_still_belongs_to_the_core() {
        Map<?, ?> health = get("/api/v1/health");
        assertThat(health.get("core")).isEqualTo(true);
        assertThat(health.get("path")).isEqualTo("/api/v1/health");
        assertThat(coreCalls.get()).isEqualTo(1);
        assertThat(webCalls.get()).isZero();
    }

    @Test
    void the_route_table_publishes_both_doors() {
        List<?> routes = client.get()
                .uri("http://localhost:" + edgePort + "/edge/routes")
                .exchange()
                .expectStatus().isOk()
                .expectBody(List.class)
                .returnResult()
                .getResponseBody();

        assertThat(routes).isNotNull();
        Map<?, ?> coreRoute = route(routes, "core-api");
        Map<?, ?> webRoute = route(routes, "web");
        assertThat(String.valueOf(coreRoute.get("uri")))
                .isEqualTo("http://127.0.0.1:" + core.getAddress().getPort());
        assertThat(String.valueOf(webRoute.get("uri")))
                .isEqualTo("http://127.0.0.1:" + web.getAddress().getPort());
        assertThat((List<?>) webRoute.get("predicates")).anyMatch(entry -> entry.toString().contains("/**"));
    }

    private static Map<?, ?> route(List<?> routes, String id) {
        return routes.stream()
                .map(Map.class::cast)
                .filter(entry -> id.equals(entry.get("id")))
                .findFirst()
                .orElseThrow(() -> new AssertionError("the resolved route table has no " + id + " route: " + routes));
    }

    private Map<?, ?> get(String path) {
        return client.get()
                .uri("http://localhost:" + edgePort + path)
                .exchange()
                .expectStatus().isOk()
                .expectHeader().exists(TraceIdFilter.TRACE_HEADER)
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
    }
}

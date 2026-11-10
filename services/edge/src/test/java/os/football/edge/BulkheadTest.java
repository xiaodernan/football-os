package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The compartment wall: /api/v1/ requests hold one permit each; the caller beyond the ceiling is
 * refused immediately in the product's shape. The web shell is a different downstream and never spends a
 * permit, and a refused call never reaches the stub core.
 *
 * <p>The ceiling is set to one through the property the real deployment reads, so admission and refusal
 * are both measured, never estimated: the first call enters the stub (and stays there until the test
 * releases it), the second is refused with {@code core_busy}, and the shell is never refused at all.
 * The stub core blocks on a latch for /api/v1/slow and answers /api/v1/fast instantly.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class BulkheadTest {

    private static HttpServer core;
    private static HttpServer web;
    private static final AtomicInteger coreCalls = new AtomicInteger();
    private static final AtomicInteger webCalls = new AtomicInteger();
    private static volatile CountDownLatch block;
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(15))
            .build();

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void stubs(DynamicPropertyRegistry registry) throws IOException {
        core = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 4);
        web = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 4);
        core.setExecutor(java.util.concurrent.Executors.newFixedThreadPool(4));
        web.setExecutor(java.util.concurrent.Executors.newFixedThreadPool(4));
        core.createContext("/api/v1/slow", exchange -> {
            coreCalls.incrementAndGet();
            try {
                CountDownLatch latch = block;
                if (latch != null) {
                    latch.await(1, TimeUnit.SECONDS);
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            respond(exchange, 200, "{\"slow\":true}");
        });
        core.createContext("/api/v1/fast", exchange -> {
            coreCalls.incrementAndGet();
            respond(exchange, 200, "{\"fast\":true}");
        });
        core.createContext("/", exchange -> {
            coreCalls.incrementAndGet();
            respond(exchange, 200, "{\"core\":true}");
        });
        web.createContext("/", exchange -> {
            webCalls.incrementAndGet();
            respond(exchange, 200, "<html>web</html>");
        });
        core.start();
        web.start();
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
        registry.add("apc.core-uri", () -> "http://127.0.0.1:" + core.getAddress().getPort());
        registry.add("apc.web-uri", () -> "http://127.0.0.1:" + web.getAddress().getPort());
        registry.add("edge.bulkhead.max-concurrent-calls", () -> "1");
    }

    private static void respond(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
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

    @BeforeEach
    void resetCounters() {
        coreCalls.set(0);
        webCalls.set(0);
    }

    private static void awaitBlockingCall() throws InterruptedException {
        long deadline = System.currentTimeMillis() + 30_000;
        while (coreCalls.get() < 1 && System.currentTimeMillis() < deadline) {
            Thread.sleep(20);
        }
        assertThat(coreCalls.get()).isEqualTo(1);
    }

    private void awaitPermit() throws InterruptedException, IOException {
        long deadline = System.currentTimeMillis() + 15_000;
        while (System.currentTimeMillis() < deadline) {
            String body = client.get()
                    .uri("http://localhost:" + edgePort + BulkheadController.PATH)
                    .exchange()
                    .expectStatus().isOk()
                    .expectBody(String.class)
                    .returnResult()
                    .getResponseBody();
            if (body != null && body.contains("\"available_concurrent_calls\":1")) {
                return;
            }
            Thread.sleep(100);
        }
        throw new AssertionError("the bulkhead permit never came back: available_concurrent_calls stayed 0");
    }

    private java.util.concurrent.CompletableFuture<String> slowAsync() {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("http://127.0.0.1:" + edgePort + "/api/v1/slow"))
                .GET()
                .build();
        return HTTP.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(HttpResponse::body);
    }

    @Test
    void beyond_the_ceiling_is_refused_immediately_in_the_product_shape() throws Exception {
        block = new CountDownLatch(1);
        var inFlight = slowAsync();
        awaitBlockingCall();

        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/slow")
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectHeader().valueEquals(HttpHeaders.RETRY_AFTER, "1")
                .expectHeader().exists(TraceIdFilter.TRACE_HEADER);
        String refusal = client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/slow")
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectBody(String.class)
                .returnResult()
                .getResponseBody();
        assertThat(refusal).contains("\"code\":\"core_busy\"");

        assertThat(coreCalls.get()).isEqualTo(1);
        // The wall's own answer for a fully-held compartment, not a race: the permit is gone,
        // refused for every /api/v1/ caller until the in-flight call returns it.
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/fast")
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectBody().jsonPath("code").isEqualTo("core_busy");
        block.countDown();
        awaitPermit();
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/fast")
                .exchange()
                .expectStatus().isOk();
    }

    @Test
    void the_shell_never_takes_a_permit() throws Exception {
        block = new CountDownLatch(1);
        var inFlight = slowAsync();
        awaitBlockingCall();

        for (int i = 0; i < 3; i++) {
            client.get()
                    .uri("http://localhost:" + edgePort + "/")
                    .exchange()
                    .expectStatus().isOk();
        }
        assertThat(webCalls.get()).isEqualTo(3);
        block.countDown();
        awaitPermit();
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/fast")
                .exchange()
                .expectStatus().isOk();
    }

    @Test
    void the_door_reports_the_live_wall() {
        client.get()
                .uri("http://localhost:" + edgePort + BulkheadController.PATH)
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("enabled").isEqualTo(true)
                .jsonPath("max_concurrent_calls").isEqualTo(1)
                .jsonPath("formula").exists();
    }
}

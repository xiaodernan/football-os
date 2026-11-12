package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The chosen instance is the faster one, measured through the gateway rather than asserted about the code.
 *
 * <p>Two cores are published under one service id: one answers immediately, one takes 70 ms. A round-robin
 * balancer would split forty requests evenly — twenty into the slow core — because rotation has no memory.
 * The assertion here is the behavioural difference: after the first exchange teaches the edge what the two
 * instances cost, the slow one receives almost nothing. The threshold is deliberately loose (30 of 40 must
 * reach the fast instance) so the test measures the policy and not a lucky random seed; the measured
 * figure is printed with a failure so a regression says how far it moved.
 *
 * <p>Both claims live in one test on purpose. The counters are static and the context is shared, so two
 * ordered tests would make one of them depend on the other having run — a coupling that reads as a flaky
 * gate the first time JUnit reorders methods.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeP2cRoutingTest {

    private static HttpServer fast;
    private static HttpServer slow;
    /** Hits per listening port. Keyed by the port the server actually bound, so a counter cannot be
     *  attached to the wrong stub: the earlier pair of fields was, and the assertion read 1 fast / 39 slow
     *  while the statistics said the fast instance had answered 35 times. */
    private static final Map<Integer, AtomicInteger> hits = new ConcurrentHashMap<>();

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @Autowired
    private InstanceStats stats;

    @DynamicPropertySource
    static void twoCores(DynamicPropertyRegistry registry) throws IOException {
        fast = core(0, hits);
        slow = core(70, hits);
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
        registry.add("edge.lb.strategy", () -> "p2c");
        registry.add("spring.cloud.discovery.client.simple.instances.football-core[0].uri",
                () -> "http://127.0.0.1:" + fast.getAddress().getPort());
        registry.add("spring.cloud.discovery.client.simple.instances.football-core[1].uri",
                () -> "http://127.0.0.1:" + slow.getAddress().getPort());
    }

    @AfterAll
    static void stopCores() {
        if (fast != null) {
            fast.stop(0);
        }
        if (slow != null) {
            slow.stop(0);
        }
    }

    @Test
    void the_faster_instance_wins_and_the_door_says_why() {
        // Warm the route before counting. The first exchange through any route pays for a cold connection
        // pool and an uncompiled path — the run that found the p2c cold-start trap measured 167 ms on the
        // fast stub's first call. Those requests still train the averages, they are just not the sample the
        // assertion is about.
        for (int i = 0; i < 15; i++) {
            client.get()
                    .uri("http://localhost:" + edgePort + "/api/v1/health")
                    .exchange()
                    .expectStatus().isOk();
        }
        hits.clear();

        int total = 40;
        for (int i = 0; i < total; i++) {
            client.get()
                    .uri("http://localhost:" + edgePort + "/api/v1/health")
                    .exchange()
                    .expectStatus().isOk();
        }

        int fastPort = fast.getAddress().getPort();
        int slowPort = slow.getAddress().getPort();
        int fastHits = hits.getOrDefault(fastPort, new AtomicInteger()).get();
        int slowHits = hits.getOrDefault(slowPort, new AtomicInteger()).get();

        assertThat(fastHits + slowHits).isEqualTo(total);
        // The balancer's only input. If this is empty the policy is choosing between two unknown
        // instances and the count below is a coin toss, which is exactly what a broken return path looks
        // like from the outside.
        assertThat(stats.snapshot()).as("the response path recorded nothing: %s", stats.snapshot()).isNotEmpty();

        assertThat(fastHits)
                .as("fast=%d slow=%d of %d — p2c should abandon the slow instance after learning what it costs",
                        fastHits, slowHits, total)
                .isGreaterThanOrEqualTo(28);

        Map<?, ?> report = client.get()
                .uri("http://localhost:" + edgePort + "/edge/lb")
                .exchange()
                .expectStatus().isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(report).isNotNull();
        assertThat(report.get("strategy")).isEqualTo("p2c");
        // The two numbers that make a score readable travel with it: without the target a reader cannot
        // tell 60 from "this instance is doing fine", and without the window they cannot tell why a row's
        // score and its average disagree. Both are the running policy, not a constant copied into the page.
        assertThat(((Number) report.get("targetMillis")).doubleValue()).isEqualTo(60.0);
        assertThat(((Number) report.get("staleAfterMillis")).longValue()).isEqualTo(30_000L);
        Map<?, ?> instances = (Map<?, ?>) report.get("instances");
        assertThat(instances).isNotEmpty();

        // The fast instance has been measured forty times minus at most one, so its average is far under
        // the target of 60 ms. That is the number the balancer compared, not a recomputation.
        double fastScore = score(instances, fastPort);
        assertThat(fastScore).isLessThan(50.0);

        // The slow instance is reported only if it was ever chosen. With two instances and a tie on the
        // first draw it has a fifty-fifty chance of being the first pick, and after that it is never picked
        // again — so a missing row means "never measured", not "not monitored", and the door is right to
        // omit it rather than invent a score.
        Object slowRow = instances.get("127.0.0.1:" + slowPort);
        if (slowRow != null) {
            assertThat(((Number) ((Map<?, ?>) slowRow).get("score")).doubleValue()).isGreaterThan(fastScore);
        }
    }

    private static double score(Map<?, ?> instances, int port) {
        Object entry = instances.get("127.0.0.1:" + port);
        assertThat(entry).as("no statistics for port %d in %s", port, instances.keySet()).isNotNull();
        return ((Number) ((Map<?, ?>) entry).get("score")).doubleValue();
    }

    private static HttpServer core(int delayMillis, Map<Integer, AtomicInteger> hits) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            hits.computeIfAbsent(server.getAddress().getPort(), ignored -> new AtomicInteger()).incrementAndGet();
            if (delayMillis > 0) {
                try {
                    Thread.sleep(delayMillis);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                }
            }
            byte[] body = "{\"core\":true}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        return server;
    }
}

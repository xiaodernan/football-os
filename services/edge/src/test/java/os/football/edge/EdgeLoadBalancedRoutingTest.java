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
 * The route the product actually runs: the core is found by name, not by address.
 *
 * <p>The stub core is not given to the gateway as `apc.core-uri`; it is published through a discovery
 * client under the service id `football-core`, exactly the way Eureka publishes a registered instance.
 * A successful request therefore proves two things a configuration file cannot: `lb://football-core`
 * resolved through the client rather than falling back, and the request arrived at the instance the
 * registry named. The route table is read back as well, because a route that silently kept a fixed
 * URI would still answer 200 while proving nothing about discovery.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeLoadBalancedRoutingTest {

    private static HttpServer core;
    private static String lastPath;

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void discoveredCore(DynamicPropertyRegistry registry) throws IOException {
        core = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        core.createContext("/", exchange -> {
            lastPath = exchange.getRequestURI().toString();
            byte[] body = ("{\"core\":true,\"path\":\"" + lastPath + "\"}").getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        core.start();
        // No apc.core-uri here on purpose. The only way to the stub is the name below.
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
        registry.add("spring.cloud.discovery.client.simple.instances.football-core[0].uri",
                () -> "http://127.0.0.1:" + core.getAddress().getPort());
    }

    @AfterAll
    static void stopCore() {
        if (core != null) {
            core.stop(0);
        }
    }

    @Test
    void the_core_is_reached_by_service_name() {
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
    }

    @Test
    void the_route_table_names_the_service_not_an_address() {
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
        assertThat(String.valueOf(route.get("uri"))).isEqualTo("lb://football-core");
    }
}

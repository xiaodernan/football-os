package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The door that answers "who would the balancer ask?".
 *
 * <p>The instance is published through the same simple discovery client the {@code lb://} route uses,
 * so the test reads the view the gateway would resolve rather than a field a controller kept for itself.
 * An unregistered name must read as zero instances, because an operator deciding between "nobody
 * registered it" and "the instance is down" needs the registry's answer and not a 404.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeInstancesTest {

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @DynamicPropertySource
    static void oneInstance(DynamicPropertyRegistry registry) {
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
        registry.add("spring.cloud.discovery.client.simple.instances.football-core[0].uri",
                () -> "http://127.0.0.1:9911");
    }

    @Test
    void the_door_reports_the_instance_the_balancer_would_use() {
        Map<?, ?> body = get("/edge/instances?service=football-core");

        assertThat(body.get("service")).isEqualTo("football-core");
        assertThat(body.get("count")).isEqualTo(1);
        List<?> instances = (List<?>) body.get("instances");
        Map<?, ?> only = (Map<?, ?>) instances.getFirst();
        assertThat(only.get("host")).isEqualTo("127.0.0.1");
        assertThat(only.get("port")).isEqualTo(9911);
        assertThat(String.valueOf(only.get("uri"))).isEqualTo("http://127.0.0.1:9911");
        assertThat(only.get("secure")).isEqualTo(false);
    }

    @Test
    void an_unregistered_service_reads_as_zero_rather_than_an_error() {
        Map<?, ?> body = get("/edge/instances?service=nobody");

        assertThat(body.get("service")).isEqualTo("nobody");
        assertThat(body.get("count")).isEqualTo(0);
        assertThat((List<?>) body.get("instances")).isEmpty();
    }

    private Map<?, ?> get(String path) {
        return client.get()
                .uri("http://localhost:" + edgePort + path)
                .exchange()
                .expectStatus().isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
    }
}

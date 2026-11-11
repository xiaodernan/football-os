package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The core registered zero instances: the caller meets the product's refusal, not a stack trace.
 *
 * <p>This is the failure the connection-refused case ({@code EdgeFallbackTest}) cannot produce and the
 * one a registry keeps producing long after a process dies — the route resolves `lb://football-core`,
 * the discovery client finds nothing, and the question is what shape the caller gets. The assertion is
 * the same one the dead-core case makes: a 503 in the product's refusal shape carrying the trace id,
 * not an internal exception page, not a silent empty string, not a 500 with a Java stack.
 */
@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
            "eureka.client.enabled=false",
            "spring.cloud.config.enabled=false"
            // No simple instances for `football-core` on purpose: the discovery client holds the name
            // with zero URIs behind it — the state a registry reports after every core has died.
        })
class EdgeZeroInstancesTest {

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @Test
    void an_empty_registry_answers_the_products_refusal_shape() {
        String supplied = "zero-instances-1";
        client.get()
                .uri("http://localhost:" + edgePort + "/api/v1/health")
                .header(TraceIdFilter.TRACE_HEADER, supplied)
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectBody()
                .jsonPath("$.code").isEqualTo("core_unavailable")
                .jsonPath("$.trace_id").isEqualTo(supplied)
                .jsonPath("$.retryable").isEqualTo(true);
    }
}

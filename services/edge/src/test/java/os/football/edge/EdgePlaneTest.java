package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * The plane door is a composition, not a second set of answers.
 *
 * <p>The strongest claim it makes is that each block equals the answer its own door gives. These cases
 * read both over HTTP and compare the parsed JSON, so a block that quietly reimplemented a predicate —
 * and then drifted — is caught here rather than in an operator's head.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgePlaneTest {

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @Autowired
    private ObjectMapper mapper;

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        registry.add("apc.core-uri", () -> "http://127.0.0.1:1");
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
        registry.add("edge.rate-limit.enabled", () -> "false");
    }

    private String text(String path) {
        byte[] body = client.get()
                .uri("http://localhost:" + edgePort + path)
                .exchange()
                .expectStatus().isOk()
                .expectBody(byte[].class)
                .returnResult()
                .getResponseBody();
        return new String(body == null ? new byte[0] : body, StandardCharsets.UTF_8);
    }

    private JsonNode read(String path) throws Exception {
        return mapper.readTree(text(path));
    }

    @Test
    void every_block_is_the_same_answer_its_own_door_gives() throws Exception {
        JsonNode plane = read(PlaneController.PATH);
        assertThat(plane.get("routes")).isEqualTo(read("/edge/routes"));
        assertThat(plane.get("limits")).isEqualTo(read("/edge/limits"));
        assertThat(plane.get("breaker")).isEqualTo(read("/edge/breaker"));
        assertThat(plane.get("instances")).isEqualTo(read("/edge/instances?service=football-core"));
        assertThat(plane.get("config")).isEqualTo(read(ConfigController.PATH));
        assertThat(plane.get("bulkhead")).isEqualTo(read(BulkheadController.PATH));
    }

    @Test
    void every_door_it_names_answers() throws Exception {
        JsonNode doors = read(PlaneController.PATH).get("doors");
        assertThat(doors.isObject()).isTrue();
        doors.fields().forEachRemaining(entry -> {
            String path = entry.getValue().asText();
            if ("/actuator/refresh".equals(path)) {
                client.post()
                        .uri("http://localhost:" + edgePort + path)
                        .contentType(MediaType.APPLICATION_JSON)
                        .bodyValue("{}")
                        .exchange()
                        .expectStatus().isOk();
            } else {
                client.get()
                        .uri("http://localhost:" + edgePort + path)
                        .exchange()
                        .expectStatus().isOk();
            }
        });
        assertThat(doors.size()).isEqualTo(7);
    }

    @Test
    void the_trace_block_names_the_headers_the_filters_really_use() throws Exception {
        JsonNode trace = read(PlaneController.PATH).get("trace");
        assertThat(trace.get("parent_header").asText()).isEqualTo(W3cTraceContextFilter.TRACE_PARENT);
        assertThat(trace.get("state_header").asText()).isEqualTo(W3cTraceContextFilter.TRACE_STATE);
        assertThat(trace.get("correlation_header").asText()).isEqualTo(TraceIdFilter.TRACE_HEADER);
    }

    @Test
    void the_plane_publishes_no_figure_of_its_own() throws Exception {
        JsonNode plane = read(PlaneController.PATH);
        assertThat(plane.fieldNames()).toIterable().containsExactlyInAnyOrder(
                "routes", "limits", "breaker", "instances", "config", "bulkhead", "trace", "doors", "formula");
        assertThat(plane.get("formula").asText()).contains("same method");
        List<?> routes = mapper.convertValue(plane.get("routes"), List.class);
        assertThat(routes).isNotEmpty();
    }
}

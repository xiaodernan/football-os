package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.cloud.context.scope.refresh.RefreshScope;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * A changed setting lands in the running gateway without a restart.
 *
 * <p>The config server has always served the edge's settings as files, but until item 59 the gateway
 * read them once at boot. These cases ask the running process, not the file: the door reads a
 * {@code @RefreshScope} bean, the refresh endpoint is exposed, and changing a property source then
 * rebuilding the scope makes the door answer with the new value.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EdgeConfigRefreshTest {

    private static final String SOURCE = "walk-overrides";

    @LocalServerPort
    private int edgePort;

    @Autowired
    private WebTestClient client;

    @Autowired
    private ConfigurableEnvironment environment;

    @Autowired
    private RefreshScope scope;

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        registry.add("edge.plane.notice", () -> "boot-notice");
        registry.add("eureka.client.enabled", () -> "false");
        registry.add("spring.cloud.config.enabled", () -> "false");
        registry.add("edge.rate-limit.enabled", () -> "false");
    }

    @AfterEach
    void dropOverrides() {
        environment.getPropertySources().remove(SOURCE);
        scope.refreshAll();
    }

    private String notice() {
        Map<?, ?> body = client.get()
                .uri("http://localhost:" + edgePort + ConfigController.PATH)
                .exchange()
                .expectStatus().isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
        assertThat(body).isNotNull();
        return String.valueOf(body.get("notice"));
    }

    @Test
    void the_settings_class_is_refresh_scoped_and_the_door_reads_the_boot_value() {
        assertThat(PlaneSettings.class.isAnnotationPresent(org.springframework.cloud.context.config.annotation.RefreshScope.class)).isTrue();
        assertThat(notice()).isEqualTo("boot-notice");
    }

    @Test
    void the_refresh_endpoint_is_exposed() {
        client.post()
                .uri("http://localhost:" + edgePort + "/actuator/refresh")
                .exchange()
                .expectStatus().isOk();
        assertThat(notice()).isEqualTo("boot-notice");
    }

    @Test
    void a_changed_setting_takes_effect_without_a_restart() {
        Map<String, Object> overrides = new HashMap<>();
        overrides.put("edge.plane.notice", "before-refresh");
        environment.getPropertySources().addFirst(new MapPropertySource(SOURCE, overrides));
        scope.refreshAll();
        assertThat(notice()).isEqualTo("before-refresh");

        overrides.put("edge.plane.notice", "after-refresh");
        scope.refreshAll();
        assertThat(notice()).isEqualTo("after-refresh");
    }
}

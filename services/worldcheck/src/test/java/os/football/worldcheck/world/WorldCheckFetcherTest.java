package os.football.worldcheck.world;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

class WorldCheckFetcherTest {

    private HttpServer server;
    private String baseUrl;

    @BeforeEach
    void start_server() throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.start();
        baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
    }

    @AfterEach
    void stop_server() {
        server.stop(0);
    }

    private void routeWorldStatus(String body, int status) {
        server.createContext("/api/v1/world/status", exchange -> {
            var bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, bytes.length);
            exchange.getResponseBody().write(bytes);
            exchange.close();
        });
    }

    @Test
    void a_well_formed_world_status_is_read() {
        routeWorldStatus("{\"version\":\"world-status-v1\",\"seed\":1234,\"counts\":{\"competitions\":12,\"teams\":40,\"players\":500,\"matches\":280,\"stat_lines\":8400,\"training_sessions\":100,\"articles\":824},\"stat_method\":{\"rating\":\"hi\"}}", 200);
        var fetcher = new WorldCheckFetcher(baseUrl, 2_000);
        var result = fetcher.fetch();
        assertThat(result.isOk()).isTrue();
        assertThat(result.status().counts().competitions()).isEqualTo(12);
        assertThat(result.status().counts().articles()).isEqualTo(824);
    }

    @Test
    void a_403_upstream_failure_carries_the_error_into_the_result() {
        routeWorldStatus("{\"code\":\"rate_limited\"}", 403);
        var fetcher = new WorldCheckFetcher(baseUrl, 2_000);
        var result = fetcher.fetch();
        assertThat(result.isOk()).isFalse();
        assertThat(result.httpCode()).isEqualTo(403);
        assertThat(result.error()).isNotNull();
    }

    @Test
    void an_unreachable_core_reads_as_zero_code_not_an_exception() {
        var fetcher = new WorldCheckFetcher("http://127.0.0.1:1", 500);
        var result = fetcher.fetch();
        assertThat(result.isOk()).isFalse();
        assertThat(result.httpCode()).isEqualTo(0);
    }
}

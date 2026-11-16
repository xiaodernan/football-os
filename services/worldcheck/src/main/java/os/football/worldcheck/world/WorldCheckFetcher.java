package os.football.worldcheck.world;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;

/**
 * The plane's fetch against the Python core. One anonymous read of `/api/v1/world/status`
 * per call; timeouts are hard; failures are captured, not thrown — a fetch that raised would
 * unstead the scheduler and red-shift the health indicator once for an issue unrelated to us.
 */
@Component
public class WorldCheckFetcher {

    private final RestClient rest;
    private final String baseUrl;

    @Autowired
    public WorldCheckFetcher(@Value("${worldcheck.world.base-url:http://localhost:8100}") String baseUrl,
                             @Value("${worldcheck.world.timeout-ms:2000}") long timeoutMs) {
        this.baseUrl = trim(baseUrl);
        this.rest = RestClient.builder()
                .requestFactory(restFactory(timeoutMs))
                .build();
    }

    /** A test seam: inject an already-built client (e.g. one bound to a mock service). */
    public WorldCheckFetcher(RestClient rest, String baseUrl) {
        this.baseUrl = trim(baseUrl);
        this.rest = rest;
    }

    private static String trim(String baseUrl) {
        return baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
    }

    private org.springframework.http.client.ClientHttpRequestFactory restFactory(long timeoutMs) {
        var restClientFactory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        restClientFactory.setConnectTimeout(Duration.ofMillis(timeoutMs));
        restClientFactory.setReadTimeout(Duration.ofMillis(timeoutMs));
        return restClientFactory;
    }

    public Result fetch() {
        Instant started = Instant.now();
        try {
            WorldStatus status = rest.get()
                    .uri(baseUrl + "/api/v1/world/status")
                    .retrieve()
                    .body(WorldStatus.class);
            return Result.ok(status != null ? status : WorldStatus.empty(), Duration.between(started, Instant.now()).toMillis());
        } catch (RestClientResponseException e) {
            // A 4xx/5xx from the door is an honest answer — record it rather than crash the scheduler
            return Result.failure(e.getStatusCode().value(), e.getResponseBodyAsString(), Duration.between(started, Instant.now()).toMillis());
        } catch (Exception e) {
            return Result.failure(0, e.getClass().getSimpleName() + ": " + e.getMessage(), Duration.between(started, Instant.now()).toMillis());
        }
    }

    public record Result(WorldStatus status, int httpCode, String error, long elapsedMs) {
        static Result ok(WorldStatus status, long elapsedMs) {
            return new Result(status, 200, null, elapsedMs);
        }

        static Result failure(int code, String error, long elapsedMs) {
            return new Result(WorldStatus.empty(), code, error, elapsedMs);
        }

        public boolean isOk() {
            return httpCode == 200;
        }
    }
}

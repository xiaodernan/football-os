package os.football.edge;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * The ceiling when there is more than one door: a token bucket kept where every replica can see it.
 *
 * <p>{@link RateLimitFilter} holds one bucket per caller <em>per process</em>. That is correct for one edge
 * and wrong for two: with N replicas behind a load balancer a caller gets N times the ceiling by spreading
 * its requests, which is exactly what a caller that is being refused will do next. This filter moves the
 * bucket into Redis and leaves the local one as the fallback.
 *
 * <p>The composition is deliberate, and it is the reason both filters still exist:
 *
 * <ul>
 *   <li>this filter runs first (order +5, before the local filter's +10);
 *   <li>when the store answers, it stamps the exchange with {@link #DECIDED_BY} and the local filter steps
 *       aside — one request is judged once, not twice, so the published ceiling is the real one;
 *   <li>when the store cannot answer within its budget, this filter steps aside and the local bucket judges.
 *       The product stays up and stays limited; only the scope shrinks, and the answer says so in
 *       {@code X-RateLimit-Scope: process}.
 * </ul>
 *
 * <p>The store call is bounded by {@code edge.rate-limit.store-timeout-ms} (default 250 ms). A rate limit is
 * not worth a queue: if the shared tier takes longer than that, the local bucket is a better answer than a
 * slower one, and the degradation counter records that it happened.
 */
@Component
public class DistributedRateLimitFilter implements GlobalFilter, Ordered {

    /** Set when the shared tier judged this request, so {@link RateLimitFilter} does not judge it again. */
    public static final String DECIDED_BY = "os.football.edge.rate.decidedBy";

    private final ObjectProvider<BucketStore> storeProvider;
    private final boolean enabled;
    private final int burst;
    private final double requestsPerSecond;
    private final List<String> trustedProxies;
    private final long storeTimeoutMs;

    private volatile long checks;
    private volatile long degradations;

    public DistributedRateLimitFilter(
            ObjectProvider<BucketStore> storeProvider,
            @Value("${edge.rate-limit.enabled:true}") boolean enabled,
            @Value("${edge.rate-limit.burst:100}") int burst,
            @Value("${edge.rate-limit.requests-per-second:50}") double requestsPerSecond,
            @Value("${edge.rate-limit.trusted-proxies:127.0.0.1/32,::1/128}") List<String> trustedProxies,
            @Value("${edge.rate-limit.store-timeout-ms:250}") long storeTimeoutMs) {
        this.storeProvider = storeProvider;
        this.enabled = enabled;
        this.burst = Math.max(1, burst);
        this.requestsPerSecond = Math.max(0.001, requestsPerSecond);
        this.trustedProxies = List.copyOf(trustedProxies);
        this.storeTimeoutMs = Math.max(1, storeTimeoutMs);
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        BucketStore store = storeProvider.getIfAvailable();
        if (!enabled || store == null) {
            return chain.filter(exchange);
        }
        String key = "football_os:edge:rate:" + CallerKey.of(exchange, trustedProxies);
        checks++;
        Mono<long[]> taken = store.take(key, burst, requestsPerSecond)
                .timeout(Duration.ofMillis(storeTimeoutMs))
                .onErrorResume(failure -> {
                    // Never logged per request: during an incident this line would be the loudest thing in
                    // the log, and the counter plus the response header already say what happened.
                    degradations++;
                    return Mono.just(BucketStore.DEGRADED);
                });
        return taken.flatMap(reply -> {
            if (reply.length < 3 || reply[0] < 0) {
                // The store could not judge; the local bucket is about to. Marking the exchange here would
                // suppress that judgement, so nothing is marked.
                return chain.filter(exchange);
            }
            exchange.getAttributes().put(DECIDED_BY, "cluster");
            if (reply[0] == 1) {
                headers(exchange, "cluster", Math.max(0, reply[1]), 0);
                return chain.filter(exchange);
            }
            return refuse(exchange, Math.max(1, (reply[2] + 999) / 1000));
        });
    }

    /** How many requests the shared tier judged, and how many it failed to judge. Read by `/edge/limits`. */
    public long checks() {
        return checks;
    }

    public long degradations() {
        return degradations;
    }

    public boolean distributed() {
        return enabled && storeProvider.getIfAvailable() != null;
    }

    @Override
    public int getOrder() {
        // After TraceIdFilter (a refusal must carry the id) and before RateLimitFilter (+10).
        return Ordered.HIGHEST_PRECEDENCE + 5;
    }

    private void headers(ServerWebExchange exchange, String scope, long remaining, long retryAfter) {
        HttpHeaders headers = exchange.getResponse().getHeaders();
        headers.set(RateLimitFilter.LIMIT_HEADER, String.valueOf(burst));
        headers.set(RateLimitFilter.REMAINING_HEADER, String.valueOf(remaining));
        headers.set("RateLimit-Limit", String.valueOf(burst));
        headers.set("RateLimit-Remaining", String.valueOf(remaining));
        headers.set("X-RateLimit-Scope", scope);
        if (retryAfter > 0) {
            headers.set(HttpHeaders.RETRY_AFTER, String.valueOf(retryAfter));
        }
    }

    private Mono<Void> refuse(ServerWebExchange exchange, long retryAfterSeconds) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.TOO_MANY_REQUESTS);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        headers(exchange, "cluster", 0, retryAfterSeconds);
        Object traceId = exchange.getAttribute(TraceIdFilter.TRACE_ATTRIBUTE);
        String body = """
                {"code":"rate_limited","message":"this caller is asking faster than the edge accepts; \
                the request was not forwarded","trace_id":"%s","at":"%s","retry_after_seconds":%d,"retryable":true,\
                "scope":"cluster"}"""
                .formatted(
                        traceId == null ? "" : traceId,
                        Instant.now(),
                        retryAfterSeconds);
        DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
        return response.writeWith(Mono.just(buffer));
    }
}

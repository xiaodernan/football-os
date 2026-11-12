package os.football.edge;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
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
 * A ceiling on how fast one caller may ask, in the product's own voice.
 *
 * <p>Every protection so far guards the core against being <em>down</em>; this one guards it against being
 * asked too much. The algorithm is a token bucket per client address: a burst allowance refilling at a
 * fixed rate. It lives at the edge because that is the only place that sees every caller before work is
 * done, and it counts nothing about football.
 *
 * <p>The refusal is not a bare 429: it carries the same `code` / `message` / `trace_id` shape the core's
 * refusals use, plus `Retry-After`, so a client can back off instead of guessing. Response headers on an
 * allowed request say the limit and what remains, which turns "why am I throttled" into a number the
 * caller can read.
 *
 * <p>Identity is the direct peer address. Behind a proxy every caller would share the proxy's address and
 * the bucket would be a global ceiling; the door is honest about that rather than trusting a forwarded
 * header a caller can type.
 */
@Component
public class RateLimitFilter implements GlobalFilter, Ordered {

    /** The configured burst: how many requests may arrive back to back. */
    public static final String LIMIT_HEADER = "X-RateLimit-Limit";

    /** What the caller has left in its bucket after this request. */
    public static final String REMAINING_HEADER = "X-RateLimit-Remaining";

    /** Kept small on purpose: a gateway holds one bucket per client address and must not grow forever. */
    private static final int MAX_TRACKED_CLIENTS = 4096;

    private final boolean enabled;
    private final int burst;
    private final double requestsPerSecond;
    private final List<String> trustedProxies;
    private final Map<String, TokenBucket> buckets;

    public RateLimitFilter(
            @Value("${edge.rate-limit.enabled:true}") boolean enabled,
            @Value("${edge.rate-limit.burst:100}") int burst,
            @Value("${edge.rate-limit.requests-per-second:50}") double requestsPerSecond,
            @Value("${edge.rate-limit.trusted-proxies:127.0.0.1/32,::1/128}") List<String> trustedProxies) {
        this.enabled = enabled;
        this.burst = Math.max(1, burst);
        this.requestsPerSecond = Math.max(0.001, requestsPerSecond);
        this.trustedProxies = List.copyOf(trustedProxies);
        this.buckets = new LinkedHashMap<>(256, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<String, TokenBucket> eldest) {
                // Access order plus this bound is the whole garbage collector: the least recently seen
                // caller is the first to be forgotten, and memory stays bounded without a timer thread.
                return size() > MAX_TRACKED_CLIENTS;
            }
        };
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        if (!enabled) {
            return chain.filter(exchange);
        }
        // The shared tier already judged this request. Judging it again would spend a second token for one
        // request, so the ceiling a caller reads would be half the ceiling it gets.
        if (exchange.getAttribute(DistributedRateLimitFilter.DECIDED_BY) != null) {
            return chain.filter(exchange);
        }
        TokenBucket bucket = bucketFor(clientKey(exchange));
        boolean allowed = bucket.tryAcquire();
        ServerHttpResponse response = exchange.getResponse();
        response.getHeaders().set(LIMIT_HEADER, String.valueOf(burst));
        response.getHeaders().set(REMAINING_HEADER, String.valueOf(bucket.remaining()));
        if (allowed) {
            return chain.filter(exchange);
        }
        return refuse(exchange, bucket);
    }

    /** Read by `/edge/limits`: the policy in force, and how many callers are being counted. */
    public boolean enabled() {
        return enabled;
    }

    public int burst() {
        return burst;
    }

    public double requestsPerSecond() {
        return requestsPerSecond;
    }

    public int trackedClients() {
        synchronized (buckets) {
            return buckets.size();
        }
    }

    @Override
    public int getOrder() {
        // After TraceIdFilter (so the refusal can carry the id) and before routing (so a refused request
        // costs nothing downstream).
        return Ordered.HIGHEST_PRECEDENCE + 10;
    }

    private Mono<Void> refuse(ServerWebExchange exchange, TokenBucket bucket) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.TOO_MANY_REQUESTS);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        response.getHeaders().set(HttpHeaders.RETRY_AFTER, String.valueOf(bucket.retryAfterSeconds(requestsPerSecond)));
        Object traceId = exchange.getAttribute(TraceIdFilter.TRACE_ATTRIBUTE);
        String body = """
                {"code":"rate_limited","message":"this caller is asking faster than the edge accepts; \
                the request was not forwarded","trace_id":"%s","at":"%s","retry_after_seconds":%d,"retryable":true}"""
                .formatted(
                        traceId == null ? "" : traceId,
                        Instant.now(),
                        bucket.retryAfterSeconds(requestsPerSecond));
        DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
        return response.writeWith(Mono.just(buffer));
    }

    private TokenBucket bucketFor(String key) {
        synchronized (buckets) {
            return buckets.computeIfAbsent(key, ignored -> new TokenBucket(burst, requestsPerSecond));
        }
    }

    /**
     * The caller, named by the same rule the Python core uses ({@link CallerKey}).
     *
     * <p>It used to be the bare peer address. That is right for a single gateway in front of the internet and
     * wrong for this product's shape: the web tier proxies a browser's calls, so every reader behind it
     * arrived as one caller, and a whole classroom shared one budget. The credential is the strongest name
     * available and it survives both NAT and the proxy hop.
     */
    private String clientKey(ServerWebExchange exchange) {
        return CallerKey.of(exchange, trustedProxies);
    }

    /** One caller's bucket. Refilled by elapsed time, never by a scheduled tick. */
    static final class TokenBucket {

        private final double capacity;
        private final double refillPerNano;
        private double tokens;
        private long lastRefillNanos;

        TokenBucket(double capacity, double perSecond) {
            this.capacity = capacity;
            this.refillPerNano = perSecond / 1_000_000_000.0;
            this.tokens = capacity;
            this.lastRefillNanos = System.nanoTime();
        }

        synchronized boolean tryAcquire() {
            refill();
            if (tokens >= 1.0) {
                tokens -= 1.0;
                return true;
            }
            return false;
        }

        synchronized long remaining() {
            refill();
            return (long) Math.floor(tokens);
        }

        synchronized long retryAfterSeconds(double perSecond) {
            refill();
            double deficit = Math.max(0.0, 1.0 - tokens);
            return Math.max(1L, (long) Math.ceil(deficit / perSecond));
        }

        private void refill() {
            long now = System.nanoTime();
            tokens = Math.min(capacity, tokens + (now - lastRefillNanos) * refillPerNano);
            lastRefillNanos = now;
        }
    }
}

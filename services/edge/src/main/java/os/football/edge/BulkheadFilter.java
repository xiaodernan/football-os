package os.football.edge;

import io.github.resilience4j.bulkhead.Bulkhead;
import io.github.resilience4j.bulkhead.BulkheadConfig;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicLong;
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
 * A ceiling on how many requests are in flight to the core at once.
 *
 * <p>The three protections already here answer three different questions: the rate limiter asks how fast
 * one caller may ask, the breaker asks whether the core is answering at all, and Retry asks whether a
 * single stumble clears. None of them bounds <em>concurrency</em>. A core that becomes slow — not down —
 * lets requests pile up at the gateway until the whole door is queued behind it. A bulkhead is the
 * compartment wall: a bounded number of in-flight calls, and everything beyond it refused immediately
 * rather than queued.
 *
 * <p>Only the API prefix occupies a permit. The web-shell route is a different downstream, and letting
 * it spend permits would refuse API calls because a page rendered. The refusal is a 503 with its own
 * code ({@code core_busy}), distinct from the breaker's {@code core_unavailable} for a core that is
 * actually down, and it carries the request's trace id and a {@code Retry-After}.
 */
@Component
public class BulkheadFilter implements GlobalFilter, Ordered {

    public static final String REFUSAL_CODE = "core_busy";
    public static final String API_PREFIX = "/api/v1/";

    private final boolean enabled;
    private final int maxConcurrentCalls;
    private final Bulkhead bulkhead;
    private final AtomicLong rejected = new AtomicLong();

    public BulkheadFilter(
            @Value("${edge.bulkhead.enabled:true}") boolean enabled,
            @Value("${edge.bulkhead.max-concurrent-calls:16}") int maxConcurrentCalls) {
        this.enabled = enabled;
        this.maxConcurrentCalls = Math.max(1, maxConcurrentCalls);
        this.bulkhead = Bulkhead.of(
                "coreBulkhead",
                BulkheadConfig.custom().maxConcurrentCalls(this.maxConcurrentCalls).build());
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        if (!enabled || !isCoreCall(exchange)) {
            return chain.filter(exchange);
        }
        if (!bulkhead.tryAcquirePermission()) {
            rejected.incrementAndGet();
            return refuse(exchange);
        }
        return chain.filter(exchange).doFinally(signal -> bulkhead.releasePermission());
    }

    private static boolean isCoreCall(ServerWebExchange exchange) {
        return exchange.getRequest().getPath().pathWithinApplication().value().startsWith(API_PREFIX);
    }

    public boolean enabled() {
        return enabled;
    }

    public int maxConcurrentCalls() {
        return maxConcurrentCalls;
    }

    public int availableConcurrentCalls() {
        return bulkhead.getMetrics().getAvailableConcurrentCalls();
    }

    public long rejected() {
        return rejected.get();
    }

    @Override
    public int getOrder() {
        // After the rate limiter: a caller already over its budget should be refused before it takes
        // a permit. Before routing, so a refused request costs the core nothing.
        return Ordered.HIGHEST_PRECEDENCE + 11;
    }

    private Mono<Void> refuse(ServerWebExchange exchange) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.SERVICE_UNAVAILABLE);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        response.getHeaders().set(HttpHeaders.RETRY_AFTER, "1");
        Object traceId = exchange.getAttribute(TraceIdFilter.TRACE_ATTRIBUTE);
        String body = """
                {"code":"core_busy","message":"the core is handling its full share of requests; \
                this one was not forwarded","trace_id":"%s","at":"%s","retry_after_seconds":1,"retryable":true}"""
                .formatted(traceId == null ? "" : traceId, Instant.now());
        DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
        return response.writeWith(Mono.just(buffer));
    }
}

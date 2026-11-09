package os.football.edge;

import java.util.UUID;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * One id per request, minted at the door if the caller did not bring one.
 *
 * <p>A request that fails in a gateway without an id is a request an operator cannot follow: the logs of
 * the edge, the core and the client have no field in common. This filter makes the id the common field.
 * It is deliberately idempotent — an id the caller supplied is the id the caller gets back, so a client's
 * own correlation id survives the hop — and it is put on the <em>response</em> before commit, because a
 * header written after the body has started is a header the caller never sees.
 */
@Component
public class TraceIdFilter implements GlobalFilter, Ordered {

    /** The header both directions carry. Lower-case in HTTP/2, read case-insensitively by every server. */
    public static final String TRACE_HEADER = "X-Trace-Id";

    /** Where the id is kept for the fallback handler: an exchange attribute, not a thread local. */
    public static final String TRACE_ATTRIBUTE = TraceIdFilter.class.getName() + ".traceId";

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String supplied = exchange.getRequest().getHeaders().getFirst(TRACE_HEADER);
        String traceId = (supplied == null || supplied.isBlank()) ? UUID.randomUUID().toString() : supplied;
        exchange.getAttributes().put(TRACE_ATTRIBUTE, traceId);
        ServerHttpRequest traced = exchange.getRequest().mutate().header(TRACE_HEADER, traceId).build();
        exchange.getResponse().beforeCommit(() -> {
            exchange.getResponse().getHeaders().set(TRACE_HEADER, traceId);
            return Mono.empty();
        });
        return chain.filter(exchange.mutate().request(traced).build());
    }

    @Override
    public int getOrder() {
        // First: everything after this — routing, the circuit breaker, the fallback — logs under the id.
        return Ordered.HIGHEST_PRECEDENCE;
    }
}

package os.football.edge;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * One response header that says how the door handled the request: the breaker's state, and whether the
 * answer came from the core or from the fallback.
 *
 * <p>Until this filter existed, a caller could see <em>that</em> it got a 503 but not <em>why</em>: a core
 * that refused the connection, a breaker that was already open, and a slow call that ran out of time all
 * produced the same status and the same body. Those are three different operational facts — one is a
 * service to restart, one is a door deliberately held shut, one is a budget to raise — and the header is
 * the cheapest place to tell them apart, because it rides on the response the caller already reads.
 *
 * <p>The value is a pair of key=value fields, not prose: {@code coreBreaker=CLOSED;outcome=pass} on the
 * happy path, {@code coreBreaker=OPEN;outcome=fallback} when the fallback answered. It is written
 * <em>before commit</em> and only if the handler has not written it already — the fallback runs inside a
 * forwarded request and owns the value there, because it knows the outcome even when the breaker is still
 * CLOSED (a connection refusal is counted by the breaker but does not open it on the first call).
 *
 * <p>The state is read lazily, at commit time, not when the filter starts: the whole point is to report
 * what the breaker thought <em>after</em> this request was counted, and reading it earlier would report
 * the state before the failure that matters.
 */
@Component
public class CircuitTraceFilter implements GlobalFilter, Ordered {

    /** The header a client or an operator can read without opening a dashboard. */
    public static final String HEADER = "X-Circuit";

    /** The default outcome: the request was routed and the core answered. */
    public static final String OUTCOME_PASS = "pass";

    /** The fallback answered instead of the core. */
    public static final String OUTCOME_FALLBACK = "fallback";

    /** Exchange attribute holding the outcome, so a later filter can correct it without a thread local. */
    public static final String ATTRIBUTE = CircuitTraceFilter.class.getName() + ".outcome";

    private final CircuitBreakerRegistry registry;

    public CircuitTraceFilter(CircuitBreakerRegistry registry) {
        this.registry = registry;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        exchange.getAttributes().putIfAbsent(ATTRIBUTE, OUTCOME_PASS);
        exchange.getResponse().beforeCommit(() -> {
            var headers = exchange.getResponse().getHeaders();
            if (!headers.containsKey(HEADER)) {
                headers.set(HEADER, describe(exchange));
            }
            return Mono.empty();
        });
        return chain.filter(exchange);
    }

    /** Builds the header value from the breaker's registry and the exchange's recorded outcome. */
    static String describe(CircuitBreakerRegistry registry, ServerWebExchange exchange) {
        String state = registry.find(BreakerController.BREAKER_NAME)
                .map(CircuitBreaker::getState)
                .map(Enum::name)
                .orElse("NOT_CREATED");
        Object outcome = exchange.getAttributes().getOrDefault(ATTRIBUTE, OUTCOME_PASS);
        return BreakerController.BREAKER_NAME + "=" + state + ";outcome=" + outcome;
    }

    private String describe(ServerWebExchange exchange) {
        return describe(registry, exchange);
    }

    @Override
    public int getOrder() {
        // Just inside the trace filter: the id exists before anything else runs, and this header is set
        // before the request reaches the route's own filters, so a route added later is covered too.
        return Ordered.HIGHEST_PRECEDENCE + 1;
    }
}

package os.football.edge;

import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * What the caller gets when the core cannot answer, in the product's own voice.
 *
 * <p>A gateway that lets a connection refusal escape as a bare 500 tells a client nothing it can act on.
 * This handler answers in the shape the API's own refusals use — a `code`, a sentence, the trace id —
 * so the edge's failures are as readable as the core's. It is registered as the circuit breaker's
 * {@code fallbackUri}, which means it runs only when the breaker is open or the forward failed.
 */
@RestController
public class FallbackHandler {

    private final CircuitBreakerRegistry registry;

    public FallbackHandler(CircuitBreakerRegistry registry) {
        this.registry = registry;
    }

    @RequestMapping("/edge/fallback")
    public Mono<ResponseEntity<Map<String, Object>>> fallback(ServerWebExchange exchange) {
        Object traceId = exchange.getAttribute(TraceIdFilter.TRACE_ATTRIBUTE);
        // The fallback knows the outcome even when the breaker is still CLOSED: the first connection
        // refusal is counted but does not open anything. Recording it here is what lets the header say
        // "fallback" instead of the default "pass" on a response that plainly did not pass.
        exchange.getAttributes().put(CircuitTraceFilter.ATTRIBUTE, CircuitTraceFilter.OUTCOME_FALLBACK);
        Map<String, Object> body = Map.of(
                "code", "core_unavailable",
                "message", "the canonical core did not answer; this is the edge speaking, not the product",
                "trace_id", traceId == null ? "" : traceId,
                "at", Instant.now().toString(),
                "retryable", true);
        return Mono.just(ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                // Set here rather than in the global filter: this response is the only one that can claim
                // an outcome the breaker may not show yet, and a header written after commit is invisible.
                .header(CircuitTraceFilter.HEADER, CircuitTraceFilter.describe(registry, exchange))
                .contentType(MediaType.APPLICATION_JSON)
                .body(body));
    }
}

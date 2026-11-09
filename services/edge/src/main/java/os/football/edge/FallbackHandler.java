package os.football.edge;

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

    @RequestMapping("/edge/fallback")
    public Mono<ResponseEntity<Map<String, Object>>> fallback(ServerWebExchange exchange) {
        Object traceId = exchange.getAttribute(TraceIdFilter.TRACE_ATTRIBUTE);
        Map<String, Object> body = Map.of(
                "code", "core_unavailable",
                "message", "the canonical core did not answer; this is the edge speaking, not the product",
                "trace_id", traceId == null ? "" : traceId,
                "at", Instant.now().toString(),
                "retryable", true);
        return Mono.just(ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .contentType(MediaType.APPLICATION_JSON)
                .body(body));
    }
}

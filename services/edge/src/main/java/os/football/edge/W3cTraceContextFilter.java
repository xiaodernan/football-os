package os.football.edge;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Locale;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * The gateway speaks the core's trace language as well as its own.
 *
 * <p>The Python core (M12 qa-proxy-gate) accepts a caller's valid W3C {@code traceparent}, drops an
 * invalid one and mints no ids of its own. {@link TraceIdFilter} already gives every request an
 * {@code X-Trace-Id}, but that header is this plane's private correlation field: on its own it leaves the
 * core's spans unparented, and a request that crosses the Java hop and the Python hop would be two
 * different traces with nothing in common. This filter puts a valid W3C trace context on the routed
 * request so the two halves of the platform share one id.
 *
 * <p>Three rules, each stated rather than assumed:
 * <ul>
 *   <li>a <em>valid</em> caller {@code traceparent} is carried through byte-for-byte, and its
 *       {@code tracestate} with it — the caller's trace stays the caller's;</li>
 *   <li>an <em>absent or invalid</em> one is replaced. An invalid {@code tracestate} is dropped too,
 *       because tracestate describes a parent that is no longer there;</li>
 *   <li>the minted trace-id is derived from the same {@code X-Trace-Id} the edge already minted (a UUID
 *       is already 32 hex digits; any other caller id is hashed into one), so the two headers name one
 *       trace. Flags are {@code 00}: the gateway does not assert sampling on a caller's behalf.</li>
 * </ul>
 *
 * <p>This is a global filter, like the id filter it follows: a route added tomorrow inherits the trace
 * context without anyone remembering to add it.
 */
@Component
public class W3cTraceContextFilter implements GlobalFilter, Ordered {

    public static final String TRACE_PARENT = "traceparent";
    public static final String TRACE_STATE = "tracestate";

    /** Version 00 is exactly four hyphen-separated fields; later versions may carry more. */
    private static final Pattern PARENT = Pattern.compile("^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$");
    private static final String ZERO_TRACE = "0".repeat(32);
    private static final String ZERO_SPAN = "0".repeat(16);
    private static final SecureRandom RANDOM = new SecureRandom();

    /** Whether a header is a well-formed, non-degenerate version-00 trace parent. */
    public static boolean isValid(String value) {
        if (value == null) {
            return false;
        }
        Matcher matched = PARENT.matcher(value);
        return matched.matches()
                && !ZERO_TRACE.equals(matched.group(1))
                && !ZERO_SPAN.equals(matched.group(2));
    }

    /** A parent whose trace-id names the same trace as the edge's correlation id. */
    public static String mint(String correlationId) {
        String bare = correlationId == null ? "" : correlationId.replace("-", "");
        String traceId = bare.matches("[0-9a-fA-F]{32}")
                ? bare.toLowerCase(Locale.ROOT)
                : UUID.nameUUIDFromBytes((correlationId == null ? "" : correlationId).getBytes(StandardCharsets.UTF_8))
                        .toString().replace("-", "").toLowerCase(Locale.ROOT);
        byte[] span = new byte[8];
        RANDOM.nextBytes(span);
        StringBuilder hex = new StringBuilder(16);
        for (byte value : span) {
            hex.append(String.format("%02x", value));
        }
        return "00-" + traceId + "-" + hex + "-00";
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String supplied = exchange.getRequest().getHeaders().getFirst(TRACE_PARENT);
        if (isValid(supplied)) {
            echo(exchange, supplied);
            return chain.filter(exchange);
        }
        String correlation = exchange.getRequest().getHeaders().getFirst(TraceIdFilter.TRACE_HEADER);
        String parent = mint(correlation);
        ServerHttpRequest traced = exchange.getRequest().mutate()
                .headers(headers -> {
                    headers.set(TRACE_PARENT, parent);
                    headers.remove(TRACE_STATE);
                })
                .build();
        ServerWebExchange routed = exchange.mutate().request(traced).build();
        echo(routed, parent);
        return chain.filter(routed);
    }

    /** The caller can read the id the core was given, not just guess it from its own request. */
    private static void echo(ServerWebExchange exchange, String parent) {
        exchange.getResponse().beforeCommit(() -> {
            exchange.getResponse().getHeaders().set(TRACE_PARENT, parent);
            return Mono.empty();
        });
    }

    @Override
    public int getOrder() {
        // One step after TraceIdFilter, whose X-Trace-Id this filter reads, and before rate limiting.
        return Ordered.HIGHEST_PRECEDENCE + 1;
    }
}

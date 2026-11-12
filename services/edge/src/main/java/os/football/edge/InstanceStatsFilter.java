package os.football.edge;

import java.net.URI;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.cloud.gateway.route.Route;
import org.springframework.cloud.gateway.support.ServerWebExchangeUtils;
import org.springframework.core.Ordered;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * Feeds the balancer's memory from the only place that knows how an exchange actually ended.
 *
 * <p>The balancer chooses an instance before the request goes out; nothing in the choice API ever hears
 * back. This filter is the return path: it sits just inside the load-balancing filter (so the request URL
 * already names the chosen instance) and records the elapsed time and the status when the exchange
 * terminates.
 *
 * <p><strong>The terminal signal is not a verdict.</strong> The first version of this filter skipped every
 * cancellation as "the caller left", which is what a cancellation means in ordinary Reactor. In the gateway
 * it means the opposite: the response body is written by Netty and the routing chain terminates by
 * cancelling its upstream, so <em>every successful proxied exchange</em> arrives here as
 * {@code SignalType.CANCEL}. Forty of forty samples were dropped, the balancer chose between two unknown
 * instances, and the measurement came back 21 of 40 — round robin wearing a new name. The status code, not
 * the signal, separates a finished answer from an abandoned one: a response that never started has no
 * status, and that is the only case worth skipping.
 *
 * <p>Two more decisions. It records only routes whose URI scheme is {@code lb} — a fixed-address route has
 * no instance to rank, and mixing the web shell's host into the core's table would put two different
 * listeners under one key. And a status below 500 counts as a success: a 404 is the core answering, not
 * the core failing, and punishing an instance for a caller's typo would exile healthy capacity.
 *
 * <p>The cost is one attribute read and one map lookup per request, on the thread that already holds the
 * exchange. There is no timer, no queue and no thread hop.
 */
@Component
public class InstanceStatsFilter implements GlobalFilter, Ordered {

    private final InstanceStats stats;

    public InstanceStatsFilter(InstanceStats stats) {
        this.stats = stats;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        long started = System.nanoTime();
        return chain.filter(exchange).doFinally(signal -> record(exchange, started));
    }

    private void record(ServerWebExchange exchange, long started) {
        HttpStatusCode status = exchange.getResponse().getStatusCode();
        if (status == null) {
            // The response never began: an abandoned call, not an instance verdict. Recording it as a
            // failure would punish a healthy server for a caller who closed a tab.
            return;
        }
        Route route = exchange.getAttribute(ServerWebExchangeUtils.GATEWAY_ROUTE_ATTR);
        if (route == null || !"lb".equals(route.getUri().getScheme())) {
            return;
        }
        URI target = exchange.getAttribute(ServerWebExchangeUtils.GATEWAY_REQUEST_URL_ATTR);
        if (target == null || target.getHost() == null || target.getPort() < 0) {
            return;
        }
        boolean ok = status.value() < 500;
        double millis = (System.nanoTime() - started) / 1_000_000.0;
        stats.record(InstanceStats.key(target), millis, ok);
    }

    @Override
    public int getOrder() {
        // One step inside ReactiveLoadBalancerClientFilter (10150): by then GATEWAY_REQUEST_URL_ATTR names
        // the instance that was chosen, not the service that was asked for.
        return 10151;
    }
}

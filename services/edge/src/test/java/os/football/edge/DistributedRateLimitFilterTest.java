package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.http.HttpStatus;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * The shared tier's four answers, without a Redis server.
 *
 * <p>A store that answers, a store that refuses, a store that fails, and a store that was never configured.
 * The last three are the ones that matter in production and the ones a live-Redis test could not exercise on
 * demand: what matters is not that Redis works, it is what the edge does when it does not.
 *
 * <p>The chain is a counter, not a mock: "the request was not forwarded" is the claim, and a counter measures
 * it. A refusal that still called the chain would look identical in the response body.
 */
class DistributedRateLimitFilterTest {

    private static ObjectProvider<BucketStore> provider(BucketStore store) {
        return new ObjectProvider<>() {
            @Override
            public BucketStore getObject() {
                return store;
            }

            @Override
            public BucketStore getObject(Object... args) {
                return store;
            }

            @Override
            public BucketStore getIfAvailable() {
                return store;
            }

            @Override
            public BucketStore getIfUnique() {
                return store;
            }
        };
    }

    private static DistributedRateLimitFilter filter(BucketStore store, boolean enabled) {
        return new DistributedRateLimitFilter(provider(store), enabled, 10, 5.0, List.of("127.0.0.1/32"), 250);
    }

    private static MockServerWebExchange exchange() {
        return MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/health")
                        .remoteAddress(new InetSocketAddress("127.0.0.1", 5555))
                        .build());
    }

    private static GatewayFilterChain counting(AtomicInteger calls) {
        return ignored -> {
            calls.incrementAndGet();
            return Mono.empty();
        };
    }

    @Test
    void an_allowed_request_is_forwarded_with_the_cluster_headers() {
        AtomicInteger calls = new AtomicInteger();
        MockServerWebExchange exchange = exchange();
        new DistributedRateLimitFilter(
                        provider((key, capacity, rps) -> {
                            assertThat(key).startsWith("football_os:edge:rate:ip:");
                            assertThat(capacity).isEqualTo(10);
                            assertThat(rps).isEqualTo(5.0);
                            return Mono.just(new long[] {1, 8, 0});
                        }),
                        true,
                        10,
                        5.0,
                        List.of("127.0.0.1/32"),
                        250)
                .filter(exchange, counting(calls))
                .block();

        assertThat(calls.get()).isEqualTo(1);
        assertThat(exchange.getResponse().getHeaders().getFirst(RateLimitFilter.REMAINING_HEADER))
                .isEqualTo("8");
        assertThat(exchange.getResponse().getHeaders().getFirst("X-RateLimit-Scope")).isEqualTo("cluster");
        assertThat(exchange.getAttributes()).containsEntry(DistributedRateLimitFilter.DECIDED_BY, "cluster");
    }

    @Test
    void a_refused_request_is_answered_here_and_not_forwarded() {
        AtomicInteger calls = new AtomicInteger();
        MockServerWebExchange exchange = exchange();
        new DistributedRateLimitFilter(
                        provider((key, capacity, rps) -> Mono.just(new long[] {0, 0, 2400})),
                        true,
                        10,
                        5.0,
                        List.of("127.0.0.1/32"),
                        250)
                .filter(exchange, counting(calls))
                .block();

        assertThat(calls.get()).isZero();
        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);
        assertThat(exchange.getResponse().getHeaders().getFirst("Retry-After")).isEqualTo("3");
        String body = exchange.getResponse().getBodyAsString().block();
        assertThat(body).contains("\"code\":\"rate_limited\"").contains("\"scope\":\"cluster\"");
    }

    @Test
    void a_broken_store_degrades_to_the_local_bucket_instead_of_refusing() {
        AtomicInteger calls = new AtomicInteger();
        MockServerWebExchange exchange = exchange();
        DistributedRateLimitFilter filter = new DistributedRateLimitFilter(
                provider((key, capacity, rps) -> Mono.error(new IllegalStateException("the store is down"))),
                true,
                10,
                5.0,
                List.of("127.0.0.1/32"),
                250);
        filter.filter(exchange, counting(calls)).block();

        assertThat(calls.get()).isEqualTo(1);
        assertThat(filter.degradations()).isEqualTo(1);
        // Nothing marks the exchange, which is what leaves the local bucket free to judge this request.
        assertThat(exchange.getAttributes()).doesNotContainKey(DistributedRateLimitFilter.DECIDED_BY);
    }

    @Test
    void a_store_that_does_not_answer_in_budget_degrades_rather_than_queueing() {
        AtomicInteger calls = new AtomicInteger();
        MockServerWebExchange exchange = exchange();
        DistributedRateLimitFilter filter = new DistributedRateLimitFilter(
                provider((key, capacity, rps) -> Mono.never()), true, 10, 5.0, List.of("127.0.0.1/32"), 40);
        filter.filter(exchange, counting(calls)).block();

        assertThat(calls.get()).isEqualTo(1);
        assertThat(filter.degradations()).isEqualTo(1);
    }

    @Test
    void without_a_store_the_filter_steps_aside_entirely() {
        AtomicInteger calls = new AtomicInteger();
        DistributedRateLimitFilter filter = filter(null, true);
        filter.filter(exchange(), counting(calls)).block();

        assertThat(calls.get()).isEqualTo(1);
        assertThat(filter.distributed()).isFalse();
        assertThat(filter.checks()).isZero();
    }

    @Test
    void a_disabled_filter_does_not_ask_the_store() {
        AtomicInteger calls = new AtomicInteger();
        AtomicInteger asked = new AtomicInteger();
        DistributedRateLimitFilter filter = new DistributedRateLimitFilter(
                provider((key, capacity, rps) -> {
                    asked.incrementAndGet();
                    return Mono.just(new long[] {1, 9, 0});
                }),
                false,
                10,
                5.0,
                List.of("127.0.0.1/32"),
                250);
        filter.filter(exchange(), counting(calls)).block();

        assertThat(calls.get()).isEqualTo(1);
        assertThat(asked.get()).isZero();
    }

    @Test
    void a_malformed_reply_is_treated_as_no_answer() {
        AtomicInteger calls = new AtomicInteger();
        MockServerWebExchange exchange = exchange();
        new DistributedRateLimitFilter(
                        provider((key, capacity, rps) -> Mono.just(new long[] {1})),
                        true,
                        10,
                        5.0,
                        List.of("127.0.0.1/32"),
                        250)
                .filter(exchange, counting(calls))
                .block();

        assertThat(calls.get()).isEqualTo(1);
        assertThat(exchange.getAttributes()).doesNotContainKey(DistributedRateLimitFilter.DECIDED_BY);
    }

    @Test
    void the_body_is_json_in_the_product_shape() {
        MockServerWebExchange exchange = exchange();
        new DistributedRateLimitFilter(provider((key, capacity, rps) -> Mono.just(new long[] {0, 0, 1000})), true, 10, 5.0, List.of(), 250)
                .filter(exchange, ignored -> Mono.empty())
                .block();
        String body = exchange.getResponse().getBodyAsString().block();
        assertThat(body).isNotNull();
        assertThat(body.getBytes(StandardCharsets.UTF_8).length).isGreaterThan(80);
        assertThat(body).contains("\"retryable\":true");
    }
}

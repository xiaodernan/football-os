package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.InetSocketAddress;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;

/**
 * One identity rule, and the three branches that decide it.
 *
 * <p>The branch that matters most is the third: a forwarded header from a peer this deployment does not
 * trust must be ignored entirely. If it were believed, a caller could mint a fresh identity per request by
 * typing a new address, and the ceiling would be decoration. The case is written as a caller presenting a
 * plausible address from an untrusted socket and being counted as the socket.
 */
class CallerKeyTest {

    private static final List<String> TRUSTED = List.of("127.0.0.1/32", "::1/128", "10.0.0.0/8");

    private static MockServerWebExchange exchange(String authorization, String forwarded, String peer) {
        MockServerHttpRequest.BaseBuilder<?> builder = MockServerHttpRequest.get("/api/v1/health");
        if (peer != null) {
            builder = builder.remoteAddress(new InetSocketAddress(peer, 4321));
        }
        if (authorization != null) {
            builder = builder.header(HttpHeaders.AUTHORIZATION, authorization);
        }
        if (forwarded != null) {
            builder = builder.header("X-Forwarded-For", forwarded);
        }
        return MockServerWebExchange.from(builder.build());
    }

    @Test
    void a_credential_names_the_caller_and_never_appears_in_the_key() {
        String key = CallerKey.of(exchange("Bearer abc.def.ghi", "203.0.113.7", "198.51.100.4"), TRUSTED);
        assertThat(key).startsWith("acct:").doesNotContain("abc.def.ghi");
        assertThat(key).hasSize("acct:".length() + 32);
    }

    @Test
    void a_credential_wins_over_a_forwarded_address() {
        String credentialed = CallerKey.of(exchange("Bearer token", "203.0.113.7", "127.0.0.1"), TRUSTED);
        String anonymous = CallerKey.of(exchange(null, "203.0.113.7", "127.0.0.1"), TRUSTED);
        assertThat(credentialed).startsWith("acct:");
        assertThat(anonymous).isEqualTo("fwd:203.0.113.7");
    }

    @Test
    void the_left_most_forwarded_entry_is_the_client() {
        // Each proxy appends, so the right-most entry is the proxy that spoke to this process — using it
        // would put every caller behind that proxy in one bucket.
        String key = CallerKey.of(exchange(null, "203.0.113.7, 10.1.2.3", "127.0.0.1"), TRUSTED);
        assertThat(key).isEqualTo("fwd:203.0.113.7");
    }

    @Test
    void a_forwarded_header_from_an_untrusted_peer_is_ignored() {
        String key = CallerKey.of(exchange(null, "203.0.113.7", "198.51.100.4"), TRUSTED);
        assertThat(key).isEqualTo("ip:198.51.100.4");
    }

    @Test
    void a_cidr_block_trusts_every_address_inside_it() {
        assertThat(CallerKey.isTrusted("10.4.5.6", List.of("10.0.0.0/8"))).isTrue();
        assertThat(CallerKey.isTrusted("11.4.5.6", List.of("10.0.0.0/8"))).isFalse();
        assertThat(CallerKey.isTrusted("127.0.0.1", List.of("127.0.0.1/32"))).isTrue();
        assertThat(CallerKey.isTrusted("127.0.0.2", List.of("127.0.0.1/32"))).isFalse();
        // A bare address is a single host, not a prefix that happens to start the same way.
        assertThat(CallerKey.isTrusted("10.0.0.1", List.of("10.0.0.1"))).isTrue();
        assertThat(CallerKey.isTrusted("10.0.0.2", List.of("10.0.0.1"))).isFalse();
    }

    @Test
    void an_exchange_with_no_peer_still_gets_one_shared_name() {
        String key = CallerKey.of(exchange(null, null, null), TRUSTED);
        assertThat(key).isEqualTo("ip:unknown");
    }
}

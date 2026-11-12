package os.football.edge;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;

/** The W3C rules are pure functions, so they are tested without booting a gateway. */
class W3cTraceContextFilterTest {

    private static final Pattern MINTED = Pattern.compile("^00-[0-9a-f]{32}-[0-9a-f]{16}-00$");

    @Test
    void a_well_formed_parent_is_valid() {
        assertThat(W3cTraceContextFilter.isValid("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")).isTrue();
    }

    @Test
    void degenerate_and_malformed_parents_are_not_valid() {
        String zeroTrace = "0".repeat(32);
        String zeroSpan = "0".repeat(16);
        assertThat(W3cTraceContextFilter.isValid(null)).isFalse();
        assertThat(W3cTraceContextFilter.isValid("")).isFalse();
        assertThat(W3cTraceContextFilter.isValid("not-a-traceparent")).isFalse();
        assertThat(W3cTraceContextFilter.isValid("00-" + zeroTrace + "-00f067aa0ba902b7-01")).isFalse();
        assertThat(W3cTraceContextFilter.isValid("00-4bf92f3577b34da6a3ce929d0e0e4736-" + zeroSpan + "-01")).isFalse();
        assertThat(W3cTraceContextFilter.isValid("00-4BF92F3577B34DA6A3CE929D0E0E4736-00f067aa0ba902b7-01")).isFalse();
        assertThat(W3cTraceContextFilter.isValid("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7")).isFalse();
    }

    @Test
    void a_minted_parent_is_a_valid_version_00_header_with_no_sampling_claim() {
        String parent = W3cTraceContextFilter.mint("walk-1234");
        assertThat(parent).matches(MINTED);
        assertThat(W3cTraceContextFilter.isValid(parent)).isTrue();
        assertThat(parent).endsWith("-00");
    }

    @Test
    void a_uuid_correlation_id_is_the_trace_id_so_both_headers_name_one_trace() {
        UUID correlation = UUID.randomUUID();
        String parent = W3cTraceContextFilter.mint(correlation.toString());
        assertThat(parent).contains("-" + correlation.toString().replace("-", "") + "-");
    }

    @Test
    void the_same_correlation_id_mints_the_same_trace_id() {
        String first = W3cTraceContextFilter.mint("walk-1234").split("-")[1];
        String second = W3cTraceContextFilter.mint("walk-1234").split("-")[1];
        assertThat(first).isEqualTo(second);
        assertThat(W3cTraceContextFilter.mint("walk-9999").split("-")[1]).isNotEqualTo(first);
    }

    @Test
    void it_follows_the_trace_id_filter_and_precedes_rate_limiting() {
        W3cTraceContextFilter filter = new W3cTraceContextFilter();
        assertThat(filter.getOrder()).isEqualTo(new TraceIdFilter().getOrder() + 1);
        assertThat(filter.getOrder()).isLessThan(new RateLimitFilter(true, 100, 50.0, java.util.List.of()).getOrder());
    }
}

package os.football.lb;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.cloud.client.DefaultServiceInstance;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.client.loadbalancer.DefaultResponse;
import org.springframework.cloud.client.loadbalancer.EmptyResponse;
import org.springframework.cloud.client.loadbalancer.Response;
import os.football.edge.InstanceStats;

/**
 * The two choices, as arithmetic: a list in, one instance out, no gateway and no clock.
 *
 * <p>The population is three instances where two answer in 3 ms and one in 400 ms. Power-of-two never has
 * to "learn" this case at request time — it draws two of three, and any pair containing the slow instance
 * compares and rejects it, so the only way the slow one is chosen is a pair that excludes the other two,
 * which is impossible with three. The test therefore asserts exactly zero over two thousand draws. If the
 * comparison ever inverts, the number is not "a bit high", it is 1333.
 */
class P2cChoiceTest {

    private static final int FAST_A = 9001;
    private static final int FAST_B = 9002;
    private static final int SLOW = 9003;

    @Test
    void the_slow_instance_is_never_chosen_when_two_faster_ones_are_present() {
        InstanceStats stats = new InstanceStats(0.5, 50, 8, 30_000);
        warm(stats, FAST_A, 3);
        warm(stats, FAST_B, 3);
        warm(stats, SLOW, 400);
        List<ServiceInstance> instances = List.of(instance(FAST_A), instance(FAST_B), instance(SLOW));

        int slow = 0;
        for (int draw = 0; draw < 2000; draw++) {
            Response<ServiceInstance> response = P2cLoadBalancer.pick(instances, stats, 0);
            assertThat(response).isInstanceOf(DefaultResponse.class);
            if (((DefaultResponse) response).getServer().getPort() == SLOW) {
                slow += 1;
            }
        }
        assertThat(slow).isZero();
    }

    @Test
    void a_failing_instance_loses_to_a_healthy_one_even_though_it_answers_faster() {
        InstanceStats stats = new InstanceStats(0.5, 50, 8, 30_000);
        // Three consecutive refusals in 1 ms. Latency alone would prefer this instance; the penalty is what
        // makes "fast but broken" lose to "slower but answering".
        for (int i = 0; i < 3; i++) {
            stats.record("127.0.0.1:" + FAST_A, 1, false);
        }
        stats.record("127.0.0.1:" + FAST_B, 80, true);
        List<ServiceInstance> instances = List.of(instance(FAST_A), instance(FAST_B));

        for (int draw = 0; draw < 200; draw++) {
            Response<ServiceInstance> response = P2cLoadBalancer.pick(instances, stats, 0);
            assertThat(((DefaultResponse) response).getServer().getPort()).isEqualTo(FAST_B);
        }
    }

    @Test
    void one_recovery_puts_a_previously_failing_instance_back_in_the_rotation() {
        InstanceStats stats = new InstanceStats(0.5, 50, 8, 30_000);
        for (int i = 0; i < 3; i++) {
            stats.record("127.0.0.1:" + FAST_A, 1, false);
        }
        stats.record("127.0.0.1:" + FAST_A, 40, true);
        // The streak is gone, so the score is the moving average again — 8 ms, after three 1 ms penalties
        // and one 40 ms success on an average that started at 50. Still under the healthy instance's 80.
        assertThat(stats.score("127.0.0.1:" + FAST_A)).isLessThan(80);
        assertThat(stats.snapshot().get("127.0.0.1:" + FAST_A).failStreak()).isZero();
    }

    @Test
    void a_single_instance_is_returned_without_a_random_draw() {
        InstanceStats stats = new InstanceStats(0.5, 50, 8, 30_000);
        Response<ServiceInstance> response = P2cLoadBalancer.pick(List.of(instance(FAST_A)), stats, 0);
        assertThat(response.hasServer()).isTrue();
        assertThat(response.getServer().getPort()).isEqualTo(FAST_A);
    }

    @Test
    void no_instances_is_an_empty_answer_not_an_invented_one() {
        InstanceStats stats = new InstanceStats(0.5, 50, 8, 30_000);
        assertThat(P2cLoadBalancer.pick(List.of(), stats, 0)).isInstanceOf(EmptyResponse.class);
    }

    @Test
    void an_unknown_instance_scores_the_target_so_a_fresh_one_is_not_starved() {
        InstanceStats stats = new InstanceStats(0.5, 50, 8, 30_000);
        assertThat(stats.score("127.0.0.1:9999")).isEqualTo(50.0);
        stats.record("127.0.0.1:9999", 10, true);
        // 50 + 0.5 * (10 - 50) = 30
        assertThat(stats.score("127.0.0.1:9999")).isEqualTo(30.0);
    }

    private static void warm(InstanceStats stats, int port, double millis) {
        for (int i = 0; i < 20; i++) {
            stats.record("127.0.0.1:" + port, millis, true);
        }
    }

    private static ServiceInstance instance(int port) {
        return new DefaultServiceInstance("core-" + port, "football-core", "127.0.0.1", port, false);
    }

    @Test
    void a_sample_inside_the_window_keeps_full_weight() {
        // The score is what the operator reads beside the average, so inside the trust horizon the two
        // must be the same number. Decay that starts at age zero made them differ on every row, always.
        InstanceStats stats = new InstanceStats(1.0, 50, 8, 30_000);
        stats.record("127.0.0.1:9001", 200, true);
        sleep(3);
        assertThat(stats.score("127.0.0.1:9001")).isEqualTo(200.0);
    }

    @Test
    void a_sample_past_the_window_fades_to_the_target() {
        InstanceStats stats = new InstanceStats(1.0, 50, 8, 1);
        stats.record("127.0.0.1:9001", 200, true);
        sleep(4);
        // Window of 1 ms, sample 4 ms old: (4 - 1) / 1 is past the end of the fade, so the reading is back
        // at the neutral target — which is the point: an instance that has not answered in a long time is
        // re-measured, not punished by an impression from an hour ago.
        assertThat(stats.score("127.0.0.1:9001")).isEqualTo(50.0);
    }

    private static void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        }
    }
}

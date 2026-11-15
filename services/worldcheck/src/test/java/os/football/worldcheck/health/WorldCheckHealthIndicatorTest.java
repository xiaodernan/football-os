package os.football.worldcheck.health;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import os.football.worldcheck.world.WorldCheckOrchestrator;
import os.football.worldcheck.world.WorldCheckResult;
import os.football.worldcheck.world.WorldCheckInvariants;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

class WorldCheckHealthIndicatorTest {

    private final WorldCheckOrchestrator orchestrator = org.mockito.Mockito.mock(WorldCheckOrchestrator.class);
    private final WorldCheckHealthIndicator health = new WorldCheckHealthIndicator(orchestrator);

    @Test
    void a_cold_start_world_reports_unknown_rather_than_an_invented_up() {
        when(orchestrator.lastResult()).thenReturn(null);

        var reading = health.health();

        assertThat(reading.getStatus().getCode()).isEqualTo("UNKNOWN");
        assertThat(reading.getDetails().get("probe")).isEqualTo("not-yet-started");
    }

    @Test
    void an_aligned_world_reports_up() {
        var aligned = new WorldCheckResult(
                Instant.now(), "ok",
                new WorldCheckResult.PlayerFace(12, 40, 500, 280, 8400, 824),
                true,
                List.of(new WorldCheckInvariants.Named("competitions", 10, 12, true)),
                List.of(),
                90L,
                "http://core",
                null);
        when(orchestrator.lastResult()).thenReturn(aligned);

        var reading = health.health();

        assertThat(reading.getDetails().get("world_aligned")).isEqualTo(true);
    }

    @Test
    void a_failed_invariant_reports_down_with_the_failing_names() {
        var down = new WorldCheckResult(
                Instant.now(), "ok",
                new WorldCheckResult.PlayerFace(12, 40, 500, 280, 8400, 824),
                false,
                List.of(new WorldCheckInvariants.Named("competitions", 10, 9, false)),
                List.of(new WorldCheckInvariants.Named("competitions", 10, 9, false)),
                90L,
                "http://core",
                null);
        when(orchestrator.lastResult()).thenReturn(down);

        var reading = health.health();
        assertThat(reading.getDetails().get("world_aligned")).isEqualTo(false);
    }
}

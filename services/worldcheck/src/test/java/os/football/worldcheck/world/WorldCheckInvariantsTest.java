package os.football.worldcheck.world;

import static org.assertj.core.api.Assertions.assertThat;

import os.football.worldcheck.world.WorldCheckInvariants.Minimum;
import os.football.worldcheck.world.WorldStatus.Counts;
import org.junit.jupiter.api.Test;

class WorldCheckInvariantsTest {

    private static final Minimum PRODUCTION_FLOOR =
            new Minimum(10, 32, 400, 200, 6000, 700);

    private static Counts counts(int competitions, int teams, int players, int matches, int statLines, int articles) {
        return new Counts(
                Integer.valueOf(competitions),
                Integer.valueOf(teams),
                Integer.valueOf(players),
                Integer.valueOf(matches),
                Integer.valueOf(statLines),
                Integer.valueOf(100),
                Integer.valueOf(articles));
    }

    @Test
    void every_count_above_the_floor_passes() {
        var status = new WorldStatus("1.0.0", 1, true,
                counts(12, 40, 500, 260, 7200, 800), java.util.Map.of());
        var invariants = WorldCheckInvariants.evaluate(status, PRODUCTION_FLOOR);

        assertThat(invariants.allPassed()).isTrue();
        assertThat(invariants.invariants()).allMatch(WorldCheckInvariants.Named::passed);
    }

    @Test
    void the_floor_column_above_expectation_fails_exactly_once() {
        var status = new WorldStatus("1.0.0", 1, true,
                counts(12, 40, 500, 260, 7200, 800), java.util.Map.of());
        var underFloor = new Minimum(13, 32, 400, 200, 6000, 700);

        var invariants = WorldCheckInvariants.evaluate(status, underFloor);

        assertThat(invariants.allPassed()).isFalse();
        assertThat(invariants.failures()).extracting(WorldCheckInvariants.Named::name)
                .containsExactlyInAnyOrder("competitions");
    }

    @Test
    void an_absent_count_is_a_failed_check_never_an_invented_zero() {
        var partial = new Counts(
                Integer.valueOf(12),
                null, // absent
                Integer.valueOf(500),
                Integer.valueOf(260),
                Integer.valueOf(7200),
                Integer.valueOf(100),
                Integer.valueOf(800));
        var status = new WorldStatus("1.0.0", 1, true, partial, java.util.Map.of());

        var invariants = WorldCheckInvariants.evaluate(status, PRODUCTION_FLOOR);

        var teamCheck = invariants.invariants().stream()
                .filter(n -> n.name().equals("teams"))
                .findFirst()
                .orElseThrow();
        assertThat(teamCheck.passed()).isFalse();
        assertThat(teamCheck.observed()).isEqualTo(-1);
    }
}

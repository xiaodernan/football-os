package os.football.worldcheck.world;

import java.util.List;

/** The list of threshold checks plus the single manager whose verdict the door prints. */
public record WorldCheckInvariants(List<Named> invariants) {

    public record Named(String name, int minimum, int observed, boolean passed) {
        // Small enough to never grow mandatory context: caller fills observed+minimum before the invariant takes a name.
        public Named withMinimum(int minimum) { return new Named(name, minimum, observed, observed >= minimum); }
    }

    public record Minimum(int competitions, int teams, int players, int matches, int statLines, int articles) {}

    public static WorldCheckInvariants evaluate(WorldStatus status, Minimum min) {
        var counts = status.counts();
        if (counts == null) {
            // An empty read is just a failed check, never an invented number.
            return new WorldCheckInvariants(List.of(
                    new Named("competitions", min.competitions(), -1, false),
                    new Named("teams", min.teams(), -1, false),
                    new Named("players", min.players(), -1, false),
                    new Named("matches", min.matches(), -1, false),
                    new Named("stat_lines", min.statLines(), -1, false),
                    new Named("articles", min.articles(), -1, false)));
        }
        return new WorldCheckInvariants(List.of(
                intInvariant("competitions", min.competitions(), counts.competitions()),
                intInvariant("teams", min.teams(), counts.teams()),
                intInvariant("players", min.players(), counts.players()),
                intInvariant("matches", min.matches(), counts.matches()),
                intInvariant("stat_lines", min.statLines(), counts.statLines()),
                intInvariant("articles", min.articles(), counts.articles())));
    }

    private static Named intInvariant(String name, int minimum, Integer observed) {
        var value = observed == null ? -1 : observed;
        return new Named(name, minimum, value, value >= minimum);
    }

    public boolean allPassed() {
        return invariants.stream().allMatch(Named::passed);
    }

    public List<Named> failures() {
        return invariants.stream().filter(n -> !n.passed()).toList();
    }
}

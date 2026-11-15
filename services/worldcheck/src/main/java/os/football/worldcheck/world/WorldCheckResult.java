package os.football.worldcheck.world;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * The answer the door prints. Carries who asked, when, how-long, and every invariant the read
 * produced — the whole verdict, not a booleans-only summary.
 */
public record WorldCheckResult(
        Instant fetchedAt,
        String version,
        PlayerFace face,
        boolean worldAligned,
        List<WorldCheckInvariants.Named> invariants,
        List<WorldCheckInvariants.Named> failures,
        long elapsedMs,
        String baseUrl,
        String error
) {
    public record PlayerFace(
            int competitions, int teams, int players, int matches, int statLines, int articles) {
        public static PlayerFace empty() {
            return new PlayerFace(0, 0, 0, 0, 0, 0);
        }

        public static PlayerFace of(WorldStatus.Counts counts) {
            if (counts == null) return empty();
            return new PlayerFace(safe(counts.competitions()), safe(counts.teams()), safe(counts.players()),
                    safe(counts.matches()), safe(counts.statLines()), safe(counts.articles()));
        }

        private static int safe(Integer value) {
            return value == null ? 0 : value;
        }
    }

    public Map<String, Object> toPayload() {
        Map<String, Object> body = new java.util.LinkedHashMap<>();
        body.put("fetched_at", fetchedAt.toString());
        body.put("version", version);
        body.put("player_face", Map.of(
                "competitions", face.competitions(),
                "teams", face.teams(),
                "players", face.players(),
                "matches", face.matches(),
                "stat_lines", face.statLines(),
                "articles", face.articles()));
        body.put("base_url", baseUrl);
        body.put("elapsed_ms", elapsedMs);
        body.put("world_aligned", worldAligned);
        body.put("invariants", invariants.stream()
                .map(n -> Map.of("name", n.name(), "minimum", n.minimum(), "observed", n.observed(), "passed", n.passed()))
                .toList());
        body.put("failures", failures.stream().map(WorldCheckInvariants.Named::name).toList());
        body.put("error", error);
        return body;
    }
}

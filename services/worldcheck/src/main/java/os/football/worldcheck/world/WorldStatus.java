package os.football.worldcheck.world;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

/**
 * The `/api/v1/world/status` payload this service verifies. Only the keys it actually relies on are
 * modelled; any new keys the core adds arrive as null-cast ignores and cost nothing. This record
 * never evaluates a football rule — it holds raw counts for arithmetic-only invariants.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record WorldStatus(
        @JsonProperty("version") String version,
        @JsonProperty("seed") Integer seed,
        @JsonProperty("auto_sync") Boolean autoSync,
        @JsonProperty("counts") Counts counts,
        @JsonProperty("stat_method") Map<String, String> statMethod
) {
    public record Counts(
            @JsonProperty("competitions") Integer competitions,
            @JsonProperty("teams") Integer teams,
            @JsonProperty("players") Integer players,
            @JsonProperty("matches") Integer matches,
            @JsonProperty("stat_lines") Integer statLines,
            @JsonProperty("training_sessions") Integer trainingSessions,
            @JsonProperty("articles") Integer articles
    ) {
        static Counts empty() {
            return new Counts(0, 0, 0, 0, 0, 0, 0);
        }
    }

    public static WorldStatus empty() {
        return new WorldStatus("unknown", null, null, Counts.empty(), Map.of());
    }
}

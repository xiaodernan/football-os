package os.football.worldcheck.world;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicReference;

/**
 * One-shot orchestrator: fetch, evaluate, remember. The scheduler and the controller both call this.
 * Two readers never need to duplicate the pipeline to see the result; the orchestrator returns the
 * sufficiency result straight and keeps the last one behind an AtomicReference for the health indicator.
 */
@Component
public class WorldCheckOrchestrator {

    private final WorldCheckFetcher fetcher;
    private final String baseUrl;
    private final WorldCheckInvariants.Minimum minimum;
    private final AtomicReference<WorldCheckResult> lastResult = new AtomicReference<>();

    public WorldCheckOrchestrator(WorldCheckFetcher fetcher,
                                  @Value("${worldcheck.world.base-url:http://localhost:8100}") String baseUrl,
                                  @Value("${worldcheck.min.competitions:10}") int minCompetitions,
                                  @Value("${worldcheck.min.teams:32}") int minTeams,
                                  @Value("${worldcheck.min.players:400}") int minPlayers,
                                  @Value("${worldcheck.min.matches:200}") int minMatches,
                                  @Value("${worldcheck.min.stat-lines:6000}") int minStatLines,
                                  @Value("${worldcheck.min.articles:700}") int minArticles) {
        this.fetcher = fetcher;
        this.baseUrl = baseUrl;
        this.minimum = new WorldCheckInvariants.Minimum(minCompetitions, minTeams, minPlayers, minMatches, minStatLines, minArticles);
    }

    /** A direct request: fetch, evaluate, remember, return. */
    public WorldCheckResult now() {
        WorldCheckFetcher.Result fetch = fetcher.fetch();
        WorldCheckResult result = evaluate(fetch, baseUrl);
        lastResult.set(result);
        return result;
    }

    /** What the scheduler has read most recently (may be absent during cold start). */
    public WorldCheckResult lastResult() {
        return lastResult.get();
    }

    private WorldCheckResult evaluate(WorldCheckFetcher.Result fetch, String baseUrl) {
        WorldCheckInvariants invariants = WorldCheckInvariants.evaluate(fetch.status(), minimum);
        var face = WorldCheckResult.PlayerFace.of(fetch.status() != null ? fetch.status().counts() : WorldStatus.Counts.empty());
        var aligned = invariants.allPassed();
        return new WorldCheckResult(
                Instant.now(),
                fetch.status() != null ? fetch.status().version() : "unknown",
                face,
                aligned,
                invariants.invariants(),
                invariants.failures(),
                fetch.elapsedMs(),
                baseUrl,
                fetch.error());
    }
}

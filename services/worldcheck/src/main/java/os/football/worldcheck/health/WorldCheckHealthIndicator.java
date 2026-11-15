package os.football.worldcheck.health;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;
import os.football.worldcheck.world.WorldCheckOrchestrator;
import os.football.worldcheck.world.WorldCheckResult;

import java.time.Duration;
import java.util.Map;

/**
 * What the plane's other services read when they ask `/actuator/health`. The world plane's verdict is
 * simply *down* when the scheduler's last probe found the core unreachable or its invariant floor low,
 * and *up* otherwise. A cold-start world that has not been probed yet returns *unknown*: better to say
 * we don't know than to lie either way.
 */
@Component
public class WorldCheckHealthIndicator implements HealthIndicator {

    private final WorldCheckOrchestrator orchestrator;

    public WorldCheckHealthIndicator(WorldCheckOrchestrator orchestrator) {
        this.orchestrator = orchestrator;
    }

    @Override
    public Health health() {
        WorldCheckResult last = orchestrator.lastResult();
        if (last == null) {
            return Health.unknown()
                    .withDetail("probe", "not-yet-started")
                    .withDetail("message", "the scheduler has not fetched the world since this process started")
                    .build();
        }
        var age = Duration.between(last.fetchedAt(), java.time.Instant.now()).toSeconds();
        Map<String, Object> detail = Map.of(
                "world_aligned", last.worldAligned(),
                "fetched_at", last.fetchedAt().toString(),
                "age_seconds", age,
                "base_url", last.baseUrl(),
                "failures", last.failures().stream().map(f -> f.name()).toList(),
                "error", last.error() != null ? last.error() : "");
        return (last.worldAligned() ? Health.up() : Health.down())
                .withDetails(detail)
                .build();
    }
}

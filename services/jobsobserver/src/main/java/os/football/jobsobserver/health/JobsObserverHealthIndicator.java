package os.football.jobsobserver.health;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;
import os.football.jobsobserver.observer.ObserverHealth;

import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * `/actuator/health` is the plane's one source of truth for "is this citizen alive". One rule,
 * mirroring the world-check indicator: we never say *up* when the observer cannot reach Redis,
 * and we never say *down* on the boot window's first second. `unknown` before the first poll,
 * `degraded`/`down` while the outage is young or persistent — the operator deserves the difference.
 */
@Component
public class JobsObserverHealthIndicator implements HealthIndicator {

    private final ObserverHealth observer;

    public JobsObserverHealthIndicator(ObserverHealth observer) {
        this.observer = observer;
    }

    @Override
    public Health health() {
        ObserverHealth.State state = observer.state();
        Map<String, Object> detail = new LinkedHashMap<>();
        detail.put("state", state.name());
        detail.put("total_polls", observer.totalPolls());
        detail.put("total_failures", observer.totalFailures());
        detail.put("last_success_at", stringOrEmpty(observer.lastSuccessAt()));
        detail.put("failure_started_at", stringOrEmpty(observer.firstFailureAt()));
        detail.put("last_error", observer.lastError() != null ? observer.lastError() : "");
        if (state == ObserverHealth.State.NONE_YET) {
            return Health.unknown().withDetails(detail).build();
        }
        if (state == ObserverHealth.State.CONNECTED) {
            detail.put("connected", true);
            return Health.up().withDetails(detail).build();
        }
        // Disconnected: degraded inside the grace window, down once the outage is provably long
        Instant outageStart = observer.firstFailureAt();
        long outageSeconds = outageStart != null ? Duration.between(outageStart, Instant.now()).getSeconds() : 0;
        detail.put("outage_seconds", outageSeconds);
        if (outageSeconds < ObserverHealth.FAILURE_GRACE.getSeconds()) {
            return Health.status("DEGRADED").withDetails(detail).build();
        }
        return Health.down().withDetails(detail).build();
    }

    private static String stringOrEmpty(Instant at) {
        return at != null ? at.toString() : "";
    }
}

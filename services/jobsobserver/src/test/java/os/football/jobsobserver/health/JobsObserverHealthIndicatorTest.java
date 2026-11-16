package os.football.jobsobserver.health;

import org.junit.jupiter.api.Test;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.Status;
import os.football.jobsobserver.observer.ObserverHealth;

import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * The indicator's contract in four lines: unknown before the first poll, up after one good one,
 * degraded while an outage is young, down once the outage outlasts the grace window.
 */
class JobsObserverHealthIndicatorTest {

    @Test
    void unknown_before_the_first_poll() {
        var health = new ObserverHealth();
        var indicator = new JobsObserverHealthIndicator(health);
        Health result = indicator.health();
        assertEquals(Status.UNKNOWN, result.getStatus());
        assertNotNull(result.getDetails().get("state"));
    }

    @Test
    void up_after_a_successful_poll() {
        var health = new ObserverHealth();
        health.recordSuccess(Instant.now());
        var indicator = new JobsObserverHealthIndicator(health);
        Health result = indicator.health();
        assertEquals(Status.UP, result.getStatus());
        assertEquals(true, result.getDetails().get("connected"));
    }

    @Test
    void degraded_while_the_outage_is_young() {
        var health = new ObserverHealth();
        health.recordFailure(Instant.now(), new RuntimeException("connection refused"));
        var indicator = new JobsObserverHealthIndicator(health);
        Health result = indicator.health();
        assertEquals(new Status("DEGRADED"), result.getStatus());
    }

    @Test
    void down_once_the_outage_outlasts_the_grace_window() {
        var health = new ObserverHealth();
        // An outage that began 31s ago — one poll, marked 31 seconds old manually.
        health.recordFailure(Instant.now().minusSeconds(31), new RuntimeException("connection refused"));
        var indicator = new JobsObserverHealthIndicator(health);
        Health result = indicator.health();
        assertEquals(Status.DOWN, result.getStatus());
        assertNotNull(result.getDetails().get("outage_seconds"));
    }
}

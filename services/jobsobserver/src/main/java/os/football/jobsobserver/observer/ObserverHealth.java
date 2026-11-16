package os.football.jobsobserver.observer;

import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.List;
import java.util.Map;

/**
 * The observer's live connection state, kept apart from the ledger so the health indicator and
 * the controller can both answer honestly without either one owning the other's figure.
 *
 * Three states exist and each means exactly what it says:
 *
 *   * {@code NONE_YET} — nothing observed yet and no poll has failed either (the boot window);
 *   * {@code CONNECTED} — the last poll answered;
 *   * {@code DISCONNECTED} — the last poll failed (the message is kept), and the health indicator
 *     reads DOWN only when the failures persist past {@link #FAILURE_GRACE}; before that it reads
 *     DEGRADED, because a brief network blip is not an outage and an operator deserves the difference.
 */
@Component
public class ObserverHealth {
    public static final Duration FAILURE_GRACE = Duration.ofSeconds(30);

    public enum State { NONE_YET, CONNECTED, DISCONNECTED }

    private volatile State state = State.NONE_YET;
    private volatile Instant lastPollAt;
    private volatile Instant lastSuccessAt;
    private volatile Instant firstFailureAt;
    private volatile String lastError;
    private long totalPolls;
    private long totalFailures;
    private final Deque<String> recentErrors = new ArrayDeque<>();

    public synchronized void recordSuccess(Instant at) {
        totalPolls++;
        state = State.CONNECTED;
        lastPollAt = at;
        lastSuccessAt = at;
        firstFailureAt = null;
        lastError = null;
    }

    public synchronized void recordFailure(Instant at, Throwable error) {
        totalPolls++;
        totalFailures++;
        if (state != State.DISCONNECTED || firstFailureAt == null) {
            firstFailureAt = at;
        }
        state = State.DISCONNECTED;
        lastPollAt = at;
        String message = error != null ? error.getMessage() : null;
        lastError = message != null ? message : (error != null ? error.getClass().getSimpleName() : "unknown");
        recentErrors.addFirst(lastError);
        while (recentErrors.size() > 4) {
            recentErrors.removeLast();
        }
    }

    public State state() { return state; }
    public Instant lastPollAt() { return lastPollAt; }
    public Instant lastSuccessAt() { return lastSuccessAt; }
    public Instant firstFailureAt() { return firstFailureAt; }
    public String lastError() { return lastError; }
    public long totalPolls() { return totalPolls; }
    public long totalFailures() { return totalFailures; }

    public synchronized List<String> recentErrors() {
        return List.copyOf(recentErrors);
    }

    public Map<String, Object> toPayload() {
        return Map.of(
                "state", state.name(),
                "connected", state == State.CONNECTED,
                "last_poll_at", stringOrEmpty(lastPollAt),
                "last_success_at", stringOrEmpty(lastSuccessAt),
                "failure_started_at", stringOrEmpty(firstFailureAt),
                "total_polls", totalPolls,
                "total_failures", totalFailures,
                "last_error", lastError != null ? lastError : "",
                "recent_errors", recentErrors());
    }

    private static String stringOrEmpty(Instant at) {
        return at != null ? at.toString() : "";
    }
}

package os.football.edge;

import java.net.URI;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * What the edge remembers about each core instance it has talked to, and the score the load balancer
 * ranks them by.
 *
 * <p>A round-robin balancer is correct only while every instance is equally good. The moment one of them
 * is slow — a garbage collection pause, a saturated connection pool, a machine whose neighbour is
 * copying a backup — round robin keeps sending it its full share, because the rotation knows nothing
 * about what came back. The result is that one bad instance costs every caller one request in N, and the
 * N-1 good instances cannot make up for it.
 *
 * <p>This class is the memory that lets the balancer see the difference. Two numbers per instance, both
 * exponential moving averages rather than window buffers: a window needs a size, a lock per append and a
 * ring index, while an EWMA is one multiply-add and one field, which matters because it is updated on the
 * response path of every proxied request.
 *
 * <p>The score is deliberately <em>not</em> latency alone. A failing instance is not merely slow, it is
 * unusable, and a 5 ms connection refusal would score better than a healthy 60 ms answer. {@code
 * failStreak} multiplies the target by a penalty, so three consecutive failures put an instance far above
 * any real latency until it answers once more.
 *
 * <p><strong>Memory goes stale, and stale memory is a trap.</strong> The first traffic through a route is
 * the most expensive traffic there is: a cold connection pool, a JIT that has not compiled the hot path,
 * a TLS handshake. Measured once, that first exchange can read three times slower than the same instance
 * reads a second later — and a balancer that trusts it will never send that instance another request,
 * so the number never corrects itself. The instance is exiled by its own first impression. The fix is
 * decay: a sample older than {@code edge.lb.stale-after-ms} is blended back toward the target, so an
 * instance that has gone quiet is re-measured instead of remembered forever.
 *
 * <p>The horizon matters, and the first version of this class had it wrong. Decay that starts at age zero
 * is decay that is always running: at 3 s into a 30 s window a 260 ms measurement already reads 237 ms,
 * so the operator's table and the moving average behind it never agree — and the reader has no way to tell
 * a genuine improvement from the clock. A sample therefore keeps <em>full</em> weight for the whole window
 * and only then fades, linearly to the target over the next window. Two consequences, both wanted: under
 * normal traffic the score equals the average it claims to be derived from, and the fade is complete at
 * twice the window, which is when a silent instance should be treated as unknown again.
 *
 * <p>An instance never seen scores at the target: neither promoted for being new nor punished for being
 * unknown. That is what keeps the balancer from starving a freshly registered instance, which is the
 * classic failure of least-connections balancers in a rolling deploy.
 */
@Component
public class InstanceStats {

    private final Map<String, Sample> samples = new ConcurrentHashMap<>();
    private final double alpha;
    private final double targetMillis;
    private final int failurePenalty;
    private final long staleAfterMillis;

    public InstanceStats(
            @Value("${edge.lb.ewma-alpha:0.3}") double alpha,
            @Value("${edge.lb.target-ms:60}") double targetMillis,
            @Value("${edge.lb.failure-penalty:8}") int failurePenalty,
            @Value("${edge.lb.stale-after-ms:30000}") long staleAfterMillis) {
        if (alpha <= 0 || alpha > 1) {
            throw new IllegalArgumentException("edge.lb.ewma-alpha must be in (0, 1], got " + alpha);
        }
        if (targetMillis <= 0) {
            throw new IllegalArgumentException("edge.lb.target-ms must be positive, got " + targetMillis);
        }
        if (failurePenalty < 1) {
            throw new IllegalArgumentException("edge.lb.failure-penalty must be at least 1, got " + failurePenalty);
        }
        if (staleAfterMillis <= 0) {
            throw new IllegalArgumentException("edge.lb.stale-after-ms must be positive, got " + staleAfterMillis);
        }
        this.alpha = alpha;
        this.targetMillis = targetMillis;
        this.failurePenalty = failurePenalty;
        this.staleAfterMillis = staleAfterMillis;
    }

    /** The key an instance is remembered under: host and port, the two fields that identify a listener. */
    public static String key(URI uri) {
        return uri.getHost() + ":" + uri.getPort();
    }

    /** The latency a healthy answer is expected to take, and the neutral score an unknown instance gets. */
    public double targetMillis() {
        return targetMillis;
    }

    /** How long a sample keeps full weight before it begins to fade toward the target. */
    public long staleAfterMillis() {
        return staleAfterMillis;
    }

    /** Folds one finished exchange into the moving average for that instance. */
    public void record(String key, double millis, boolean ok) {
        samples.computeIfAbsent(key, ignored -> new Sample(targetMillis)).observe(millis, ok, alpha);
    }

    /** Lower is better. Unknown instances sit at the target, which is the neutral middle of the range. */
    public double score(String key) {
        Sample sample = samples.get(key);
        return sample == null ? targetMillis : sample.score(targetMillis, failurePenalty, staleAfterMillis);
    }

    /** The whole memory, for the door an operator reads. Ordered by score so the worst instance is first. */
    public Map<String, Snapshot> snapshot() {
        Map<String, Snapshot> report = new LinkedHashMap<>();
        samples.entrySet().stream()
                .map(entry -> Map.entry(entry.getKey(), entry.getValue().snapshot(targetMillis, failurePenalty, staleAfterMillis)))
                .sorted((left, right) -> Double.compare(right.getValue().score(), left.getValue().score()))
                .forEach(entry -> report.put(entry.getKey(), entry.getValue()));
        return report;
    }

    /** One instance's memory as it stood when read: what the balancer used, not a recomputation. */
    public record Snapshot(
            double score,
            double ewmaMillis,
            int failStreak,
            long observations,
            long failures,
            double lastMillis,
            long ageMillis) {}

    /** One instance's moving average. Synchronised because two event-loop threads may finish together. */
    private static final class Sample {

        private double ewma;
        private int failStreak;
        private long observations;
        private long failures;
        private double lastMillis;
        private long lastObservedNanos;

        Sample(double initial) {
            this.ewma = initial;
            this.lastObservedNanos = System.nanoTime();
        }

        synchronized void observe(double millis, boolean ok, double alpha) {
            ewma = ewma * (1 - alpha) + millis * alpha;
            lastMillis = millis;
            observations += 1;
            lastObservedNanos = System.nanoTime();
            if (ok) {
                failStreak = 0;
            } else {
                failStreak += 1;
                failures += 1;
            }
        }

        synchronized double score(double target, int penalty, long staleAfterMillis) {
            double base = failStreak == 0 ? ewma : ewma + (double) failStreak * penalty * target;
            // Whole milliseconds, so a sample read in the same millisecond it was taken is exactly itself.
            // A nanosecond clock here made a fresh 200 ms reading print as 199.9999925 in the very next
            // statement, which is the kind of "almost equal" that turns an assertion into a tolerance.
            long ageMillis = (System.nanoTime() - lastObservedNanos) / 1_000_000L;
            if (ageMillis <= staleAfterMillis) {
                // Inside the trust horizon the score *is* the measurement. Decaying from age zero made the
                // operator's table disagree with the average beside it on every row, always.
                return base;
            }
            // Past the horizon the sample fades linearly, reaching the neutral target at twice the window:
            // an instance that has not answered in two windows is indistinguishable from an unknown one.
            double fade = Math.min(1.0, (double) (ageMillis - staleAfterMillis) / staleAfterMillis);
            return base * (1 - fade) + target * fade;
        }

        synchronized Snapshot snapshot(double target, int penalty, long staleAfterMillis) {
            long ageMillis = (System.nanoTime() - lastObservedNanos) / 1_000_000L;
            return new Snapshot(score(target, penalty, staleAfterMillis), ewma, failStreak, observations, failures, lastMillis, ageMillis);
        }
    }
}

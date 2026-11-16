package os.football.jobsobserver.observer;

import java.time.Instant;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * The observer's honest memory: a bounded, ordered, thread-safe ledger of what crossed the stream.
 *
 * Two bounds are deliberate, and both are written down at their own site:
 *
 *   * <b>Type table bounded at {@value #MAX_TRACKED_TYPES}</b>. A poison message naming a
 *     brand-new job type must not grow this map without limit. Once the table is full, the
 *     commensurate types sum into a single {@code other} bucket — a count is still a count,
 *     and the shape of the answer never lies.
 *   * <b>Recent ids ring at {@value #RECENT_ID_COUNT}</b>. Enough for a terminal reader to
 *     spot a loop; small enough to never matter.
 *
 * Pure arithmetic. Nothing here knows what a job type means; the Python core does.
 */
public final class StreamLedger {
    public static final int MAX_TRACKED_TYPES = 64;
    public static final int RECENT_ID_COUNT = 8;
    public static final String OTHER_BUCKET = "other";

    private final String stream;
    private final String group;
    private final String consumer;
    private final Instant startedAt = Instant.now();

    private long totalObserved;
    private long unknownTypeObserved;
    private String lastRecordId;
    private Instant firstSeenAt;
    private Instant lastSeenAt;
    private final Map<String, Long> perType = new LinkedHashMap<>();
    private final String[] recentIds = new String[RECENT_ID_COUNT];
    private int recentCursor;

    public StreamLedger(String stream, String group, String consumer) {
        this.stream = stream;
        this.group = group;
        this.consumer = consumer;
    }

    public synchronized void observe(String jobType, String recordId, Instant at) {
        totalObserved++;
        firstSeenAt = firstSeenAt != null ? firstSeenAt : at;
        lastSeenAt = at;
        String key = normalize(jobType);
        if (!perType.containsKey(key)) {
            if (perType.size() >= MAX_TRACKED_TYPES) {
                unknownTypeObserved++;
                key = OTHER_BUCKET;
            }
        }
        perType.merge(key, 1L, Long::sum);
        lastRecordId = recordId;
        recentIds[recentCursor % RECENT_ID_COUNT] = recordId;
        recentCursor = recentCursor + 1;
    }

    static String normalize(String jobType) {
        if (jobType == null) return "unknown";
        String trimmed = jobType.trim();
        return trimmed.isEmpty() ? "unknown" : trimmed;
    }

    public synchronized Map<String, Object> snapshot() {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("stream", stream);
        payload.put("group", group);
        payload.put("consumer", consumer);
        payload.put("started_at", startedAt.toString());
        payload.put("total_observed", totalObserved);
        payload.put("unnamed_hints", unknownTypeObserved);
        payload.put("per_type", Collections.unmodifiableMap(new LinkedHashMap<>(perType)));
        payload.put("last_record_id", lastRecordId);
        payload.put("first_seen_at", firstSeenAt != null ? firstSeenAt.toString() : null);
        payload.put("last_seen_at", lastSeenAt != null ? lastSeenAt.toString() : null);
        payload.put("recent_record_ids", recentIdsSnapshot());
        payload.put("other_bucket", OTHER_BUCKET);
        payload.put("max_tracked_types", MAX_TRACKED_TYPES);
        return payload;
    }

    private java.util.List<String> recentIdsSnapshot() {
        java.util.List<String> out = new java.util.ArrayList<>(RECENT_ID_COUNT);
        if (recentCursor == 0) return out;
        int size = Math.min(recentCursor, RECENT_ID_COUNT);
        // Walk backwards from the newest write so readers get newest-first order.
        for (int i = 1; i <= size; i++) {
            int idx = Math.floorMod(recentCursor - i, RECENT_ID_COUNT);
            String value = recentIds[idx];
            if (value != null) out.add(value);
        }
        return out;
    }

    public String stream() { return stream; }
    public String group() { return group; }
    public String consumer() { return consumer; }

    /** Visible for tests: is this record id inside the recent ring? */
    Optional<String> mostRecent() { return Optional.ofNullable(lastRecordId); }
}

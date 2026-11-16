package os.football.jobsobserver.observer;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The ledger's guarantees, restated as the contract the plane relies on: every hint counted,
 * unnamed hints counted, the type table bounded by MAX_TRACKED_TYPES with an "other" bucket, the
 * recent ring newest-first, and the snapshot stable under repeated observation.
 */
class StreamLedgerTest {

    @Test
    void every_hint_increments_its_type_and_the_total() {
        StreamLedger ledger = new StreamLedger("football_os:jobs", "football_os:jobs:observers", "jobs-observer-test");
        Instant t0 = Instant.parse("2026-11-16T00:00:00Z");
        ledger.observe("video", "1-1", t0);
        ledger.observe("video", "2-1", t0.plusSeconds(1));
        ledger.observe("clips", "3-1", t0.plusSeconds(2));

        Map<String, Object> snapshot = ledger.snapshot();
        assertEquals(3L, snapshot.get("total_observed"));
        assertEquals(Map.of("video", 2L, "clips", 1L), snapshot.get("per_type"));
        assertEquals("3-1", snapshot.get("last_record_id"));
        assertEquals(t0.toString(), snapshot.get("first_seen_at"));
        assertEquals(t0.plusSeconds(2).toString(), snapshot.get("last_seen_at"));
        assertEquals(List.of("3-1", "2-1", "1-1"), snapshot.get("recent_record_ids"));
    }

    @Test
    void unnamed_types_are_counted_not_dropped() {
        StreamLedger ledger = new StreamLedger("s", "g", "c");
        Instant t0 = Instant.now();
        ledger.observe("   ", "4-1", t0);
        ledger.observe(null, "5-1", t0);
        Map<String, Object> snapshot = ledger.snapshot();
        assertEquals(Map.of("unknown", 2L), snapshot.get("per_type"));
    }

    @Test
    void the_type_table_is_bounded_and_overflow_sums_into_other() {
        StreamLedger ledger = new StreamLedger("s", "g", "c");
        Instant t0 = Instant.now();
        for (int i = 0; i < StreamLedger.MAX_TRACKED_TYPES; i++) {
            ledger.observe("type-" + i, "r-" + i, t0);
        }
        ledger.observe("late-type-one", "r-late-1", t0);
        ledger.observe("late-type-two", "r-late-2", t0);

        Map<String, Object> snapshot = ledger.snapshot();
        @SuppressWarnings("unchecked")
        Map<String, Long> perType = (Map<String, Long>) snapshot.get("per_type");
        assertEquals(StreamLedger.MAX_TRACKED_TYPES + 1, perType.size()); // 64 known + "other"
        assertEquals(2L, perType.get(StreamLedger.OTHER_BUCKET));
        assertEquals(2L, snapshot.get("unnamed_hints"));
        assertEquals(StreamLedger.MAX_TRACKED_TYPES + 2L, snapshot.get("total_observed"));
    }

    @Test
    void the_recent_ring_returns_newest_first_and_never_grows() {
        StreamLedger ledger = new StreamLedger("s", "g", "c");
        Instant t0 = Instant.now();
        for (int i = 0; i < StreamLedger.RECENT_ID_COUNT + 3; i++) {
            ledger.observe("video", "id-" + i, t0.plusSeconds(i));
        }
        Map<String, Object> snapshot = ledger.snapshot();
        @SuppressWarnings("unchecked")
        List<String> recent = (List<String>) snapshot.get("recent_record_ids");
        assertEquals(StreamLedger.RECENT_ID_COUNT, recent.size());
        assertEquals("id-10", recent.get(0));
        assertEquals("id-3", recent.get(recent.size() - 1));
    }

    @Test
    void snapshot_keeps_the_declared_contract_keys() {
        StreamLedger ledger = new StreamLedger("football_os:jobs", "football_os:jobs:observers", "jobs-observer-test");
        Map<String, Object> snapshot = ledger.snapshot();
        assertTrue(snapshot.keySet().containsAll(List.of(
                "stream", "group", "consumer", "started_at",
                "total_observed", "unnamed_hints", "per_type",
                "last_record_id", "first_seen_at", "last_seen_at",
                "recent_record_ids", "other_bucket", "max_tracked_types")));
    }
}

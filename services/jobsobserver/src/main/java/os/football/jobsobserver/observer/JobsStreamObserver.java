package os.football.jobsobserver.observer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.connection.stream.Consumer;
import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.connection.stream.ReadOffset;
import org.springframework.data.redis.connection.stream.RecordId;
import org.springframework.data.redis.connection.stream.StreamOffset;
import org.springframework.data.redis.connection.stream.StreamReadOptions;
import org.springframework.data.redis.core.StreamOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.time.Duration;
import java.time.Instant;
import java.util.List;

/**
 * The poller. One responsibility per statement, by order of operations in {@link #poll()}:
 *
 *   1. make sure the consumer group exists (idempotent; "BUSYGROUP" is a success, not a failure);
 *   2. block-read up to {@link #BATCH} hints from the ">" offset — never from history — for at
 *      most {@link #BLOCK};
 *   3. for each hint: update the ledger, ack this consumer's own record;
 *   4. refresh the health line — never throw past this point, so a scheduler tick cannot tear down
 *      the process; the health line is how the plane finds out.
 *
 * The observer never creates the stream (one observer must not decide when the jobs broker is
 * healthy by materialising it), never marks anything delivered elsewhere, and never interprets
 * the payload. A hint it cannot parse is counted as `unknown` and acked — an operator's eye
 * belongs on the dead-letter stream, not on an observer loop.
 */
@Service
public class JobsStreamObserver {

    public static final int BATCH = 32;
    public static final Duration BLOCK = Duration.ofSeconds(1);

    private static final Logger log = LoggerFactory.getLogger(JobsStreamObserver.class);

    private final StreamOperations<String, String, String> streams;
    private final ObserverHealth health;
    private final StreamLedger ledger;
    private final String key;
    private final String group;
    private final String consumer;
    private volatile boolean groupEnsured;

    public JobsStreamObserver(StringRedisTemplate redis,
                              ObserverHealth health,
                              @Value("${jobsobserver.stream:football_os:jobs}") String key,
                              @Value("${jobsobserver.group:football_os:jobs:observers}") String group) {
        this.streams = redis.opsForStream();
        this.health = health;
        this.ledger = new StreamLedger(key, group, consumerName());
        this.key = key;
        this.group = group;
        this.consumer = ledger.consumer();
    }

    /** One poll. Scheduled by {@link os.football.jobsobserver.scheduler.JobObserverScheduler}. */
    public void poll() {
        Instant now = Instant.now();
        try {
            ensureGroup();
            var options = StreamReadOptions.empty()
                    .count(BATCH)
                    .block(BLOCK);
            List<MapRecord<String, String, String>> records = streams.read(
                    Consumer.from(group, consumer),
                    options,
                    StreamOffset.create(key, ReadOffset.from(">")));
            if (records != null) {
                for (MapRecord<String, String, String> record : records) {
                    String jobType = record.getValue().get("type");
                    ledger.observe(
                            jobType != null ? jobType : record.getValue().get("job_type"),
                            record.getId().getValue(),
                            Instant.now());
                    streams.acknowledge(key, group, record.getId().getValue());
                }
            }
            health.recordSuccess(now);
        } catch (Exception error) {
            // A missing stream ("ERR no such key") is the poll's own news, not a reason to hide:
            // record the failure; the health line will print it as-is. The stack goes to the log
            // every time — silent failure is how "it looked fine on the terminal" incidents start.
            health.recordFailure(now, error);
            log.warn("jobs observer poll failed ({}): {}", error.getClass().getSimpleName(), error.toString(), error);
        }
    }

    private void ensureGroup() {
        if (groupEnsured) {
            return;
        }
        try {
            streams.createGroup(key, ReadOffset.from("$"), group);
            groupEnsured = true;
        } catch (Exception error) {
            if (isBusyGroup(error)) {
                // `$` offset on an existing (key, group) pair: exactly the steady state across restarts.
                groupEnsured = true;
                return;
            }
            throw error;
        }
    }

    static boolean isBusyGroup(Throwable error) {
        for (Throwable t = error; t != null; t = t.getCause()) {
            String message = t.getMessage();
            if (message != null && message.contains("BUSYGROUP")) return true;
        }
        return false;
    }

    private String consumerName() {
        try {
            return "jobs-observer-" + InetAddress.getLocalHost().getHostName();
        } catch (UnknownHostException error) {
            return "jobs-observer-sandbox";
        }
    }

    public StreamLedger ledger() { return ledger; }

    public boolean streamExists() {
        try {
            return streams.size(key) != null;
        } catch (Exception error) {
            return false;
        }
    }

    public Long streamLength() {
        try {
            return streamExists() ? streams.size(key) : null;
        } catch (Exception error) {
            return null;
        }
    }

    public Long pendingCount() {
        try {
            return streams.pending(key, group).getTotalPendingMessages();
        } catch (Exception error) {
            return null;
        }
    }

    /** Test seam: the fresh group flag is re-armed so a fixture can drive ensureGroup again. */
    public void rearmGroupForTests() {
        this.groupEnsured = false;
    }
}

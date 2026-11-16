package os.football.jobsobserver.web;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import os.football.jobsobserver.observer.JobsStreamObserver;
import os.football.jobsobserver.observer.ObserverHealth;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The terminal door. One route, one figure per line: what was seen, what the health line thinks,
 * whether the broker stream exists, how long it is and what is still pending our consumer group.
 *
 * Like the world-check door, this never turns a fault into a 500: a door a plane operator pokes
 * with curl on a live incident answers with the honest payload it has, not an error page.
 */
@RestController
public class JobsObserverController {

    private final JobsStreamObserver observer;
    private final ObserverHealth health;

    public JobsObserverController(JobsStreamObserver observer, ObserverHealth health) {
        this.observer = observer;
        this.health = health;
    }

    @GetMapping("/jobs/observer")
    public ResponseEntity<Map<String, Object>> observer() {
        Map<String, Object> payload = new LinkedHashMap<>(observer.ledger().snapshot());
        payload.put("connection", health.toPayload());
        payload.put("stream_length", observer.streamLength());
        payload.put("pending_messages", observer.pendingCount());
        payload.put("stream_exists", observer.streamExists());
        return ResponseEntity.ok(payload);
    }
}

package os.football.worldcheck.web;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import os.football.worldcheck.world.WorldCheckOrchestrator;
import os.football.worldcheck.world.WorldCheckResult;

import java.util.Map;

/**
 * The door the plane's operators hit on a terminal. Two routes: live (+ fetch), last (scheduler's most
 * recent read). Neither route ever fails the plane: on an upstream error the door returns 200 with the
 * failure envelope — the fault is the answer, not a crash.
 */
@RestController
public class WorldCheckController {

    private final WorldCheckOrchestrator orchestrator;

    public WorldCheckController(WorldCheckOrchestrator orchestrator) {
        this.orchestrator = orchestrator;
    }

    @GetMapping("/world/check")
    public ResponseEntity<Map<String, Object>> check() {
        return ResponseEntity.ok(orchestrator.now().toPayload());
    }

    @GetMapping("/world/check/cached")
    public ResponseEntity<Map<String, Object>> cached() {
        var last = orchestrator.lastResult();
        if (last == null) {
            return ResponseEntity.status(HttpStatus.PRECONDITION_REQUIRED)
                    .body(Map.of("error", "worldcheck-not-yet",
                            "message", "the scheduler has not fetched the world since this process started"));
        }
        return ResponseEntity.ok(last.toPayload());
    }
}

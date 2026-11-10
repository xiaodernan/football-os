package os.football.edge;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** What the compartment wall is holding right now, read from the live semaphore. */
@RestController
public class BulkheadController {

    public static final String PATH = "/edge/bulkhead";

    private final BulkheadFilter filter;

    public BulkheadController(BulkheadFilter filter) {
        this.filter = filter;
    }

    @GetMapping(PATH)
    public Map<String, Object> report() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("enabled", filter.enabled());
        body.put("max_concurrent_calls", filter.maxConcurrentCalls());
        body.put("available_concurrent_calls", filter.availableConcurrentCalls());
        body.put("rejected", filter.rejected());
        body.put("formula", "one permit per in-flight /api/v1/ request; a request finding none gets 503 core_busy immediately, and the web shell never takes a permit");
        return body;
    }
}

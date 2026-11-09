package os.football.edge;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The rate policy in force, read from the filter that enforces it.
 *
 * <p>Like `/edge/routes`, this door answers about the edge itself so an operator does not have to infer
 * behaviour from a configuration file that may have been overridden by a profile or the config server.
 * It says nothing about football and forwards nothing.
 */
@RestController
public class LimitsController {

    private final RateLimitFilter filter;

    public LimitsController(RateLimitFilter filter) {
        this.filter = filter;
    }

    @GetMapping("/edge/limits")
    public LimitPolicy limits() {
        return new LimitPolicy(filter.enabled(), filter.requestsPerSecond(), filter.burst(), filter.trackedClients());
    }

    /** What one caller may do, and how many callers are currently being counted. */
    public record LimitPolicy(boolean enabled, double requestsPerSecond, int burst, int trackedClients) {}
}

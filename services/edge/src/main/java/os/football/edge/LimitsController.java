package os.football.edge;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The rate policy in force, read from the filters that enforce it.
 *
 * <p>Like `/edge/routes`, this door answers about the edge itself so an operator does not have to infer
 * behaviour from a configuration file that may have been overridden by a profile or the config server.
 * It says nothing about football and forwards nothing.
 *
 * <p>Since M15 there are two tiers and the answer names both, because "what is my limit" now depends on
 * which one judged the last request: {@code distributed} says whether the shared store is in the path at
 * all, {@code checks} how many requests it judged, and {@code degradations} how many it failed to — each of
 * those being a request that fell back to the process's own bucket, which is a limit with a different scope.
 */
@RestController
public class LimitsController {

    private final RateLimitFilter filter;
    private final DistributedRateLimitFilter distributed;

    public LimitsController(RateLimitFilter filter, DistributedRateLimitFilter distributed) {
        this.filter = filter;
        this.distributed = distributed;
    }

    @GetMapping("/edge/limits")
    public LimitPolicy limits() {
        return new LimitPolicy(
                filter.enabled(),
                filter.requestsPerSecond(),
                filter.burst(),
                filter.trackedClients(),
                distributed.distributed(),
                distributed.checks(),
                distributed.degradations());
    }

    /** What one caller may do, how many callers are counted, and which tier is answering. */
    public record LimitPolicy(
            boolean enabled,
            double requestsPerSecond,
            int burst,
            int trackedClients,
            boolean distributed,
            long distributedChecks,
            long distributedDegradations) {}
}

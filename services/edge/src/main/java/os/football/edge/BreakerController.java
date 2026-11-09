package os.football.edge;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import java.util.Optional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The breaker's actual state, read from the registry that the route's filter writes to.
 *
 * <p>The route protects the core with a circuit breaker named `coreBreaker`, but until now the only way
 * to know what it thought was to make a request and watch what happened. This door answers the question
 * directly — state, buffered calls, failures, the thresholds in force — so an operator can tell "the core
 * is down" from "the breaker is still holding the door shut" without reading a log.
 *
 * <p>`present=false` is honest: a breaker is created lazily on the first routed call, so before any
 * traffic there is nothing to report and the door says so instead of inventing a CLOSED state.
 */
@RestController
public class BreakerController {

    static final String BREAKER_NAME = "coreBreaker";

    private final CircuitBreakerRegistry registry;

    public BreakerController(CircuitBreakerRegistry registry) {
        this.registry = registry;
    }

    @GetMapping("/edge/breaker")
    public BreakerReport breaker() {
        Optional<CircuitBreaker> found = registry.find(BREAKER_NAME);
        if (found.isEmpty()) {
            return BreakerReport.absent(BREAKER_NAME);
        }
        CircuitBreaker breaker = found.get();
        CircuitBreaker.Metrics metrics = breaker.getMetrics();
        var config = breaker.getCircuitBreakerConfig();
        return new BreakerReport(
                BREAKER_NAME,
                true,
                breaker.getState().name(),
                config.getSlidingWindowSize(),
                config.getFailureRateThreshold(),
                config.getMinimumNumberOfCalls(),
                config.getPermittedNumberOfCallsInHalfOpenState(),
                metrics.getNumberOfBufferedCalls(),
                metrics.getNumberOfFailedCalls(),
                metrics.getNumberOfSuccessfulCalls(),
                metrics.getNumberOfNotPermittedCalls(),
                metrics.getFailureRate());
    }

    /** One moment of one breaker: its state, its rolling window, and the thresholds it enforces. */
    public record BreakerReport(
            String name,
            boolean present,
            String state,
            int slidingWindowSize,
            float failureRateThreshold,
            int minimumNumberOfCalls,
            int permittedCallsInHalfOpenState,
            int bufferedCalls,
            int failedCalls,
            int successfulCalls,
            long notPermittedCalls,
            float failureRate) {

        static BreakerReport absent(String name) {
            return new BreakerReport(name, false, "NOT_CREATED", 0, 0f, 0, 0, 0, 0, 0, 0L, -1f);
        }
    }
}

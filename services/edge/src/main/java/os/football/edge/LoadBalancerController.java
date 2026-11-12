package os.football.edge;

import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * What the balancer currently believes about each core instance.
 *
 * <p>A load-balancing policy that cannot be read is a policy nobody can defend in an incident: the
 * question "why did every request go to one instance" has an answer, and it is a table of scores, not a
 * guess. This door prints that table — the score the decision uses, the moving average behind it, the
 * failure streak, and how many exchanges were counted — ordered worst first.
 *
 * <p>{@code instances} is empty before the first routed request, and says so rather than inventing rows:
 * the memory is built from answers, and there have been none.
 *
 * <p>The two parameters travel with the table because a score without its window cannot be read. {@code
 * targetMillis} is the neutral value — what an instance that has never answered scores, and what a faded
 * sample converges to — and {@code staleAfterMillis} is how long a measurement keeps full weight before it
 * begins to fade. An operator who sees {@code 60} beside an average of {@code 260} should be able to tell
 * from the payload alone that the row is old rather than wrong; the console page is the first reader that
 * needed to.
 */
@RestController
public class LoadBalancerController {

    private final InstanceStats stats;
    private final String strategy;

    public LoadBalancerController(InstanceStats stats, @Value("${edge.lb.strategy:p2c}") String strategy) {
        this.stats = stats;
        this.strategy = strategy;
    }

    @GetMapping("/edge/lb")
    public Report report() {
        return new Report(strategy, stats.targetMillis(), stats.staleAfterMillis(), stats.snapshot());
    }

    /** The policy in force, the two numbers that give its scores meaning, and the table it decides by. */
    public record Report(
            String strategy, double targetMillis, long staleAfterMillis, Map<String, InstanceStats.Snapshot> instances) {}
}

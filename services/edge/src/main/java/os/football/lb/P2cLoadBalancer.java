package os.football.lb;

import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.client.loadbalancer.DefaultResponse;
import org.springframework.cloud.client.loadbalancer.EmptyResponse;
import org.springframework.cloud.client.loadbalancer.Request;
import org.springframework.cloud.client.loadbalancer.Response;
import org.springframework.cloud.loadbalancer.core.NoopServiceInstanceListSupplier;
import org.springframework.cloud.loadbalancer.core.ReactorServiceInstanceLoadBalancer;
import org.springframework.cloud.loadbalancer.core.ServiceInstanceListSupplier;
import org.springframework.cloud.loadbalancer.support.LoadBalancerClientFactory;
import org.springframework.core.env.Environment;
import os.football.edge.InstanceStats;
import reactor.core.publisher.Mono;

/**
 * Power of two choices, over latency the edge has actually measured — plus a small deliberate mistake.
 *
 * <p>Round robin is a fixed permutation: it spreads requests evenly by construction and therefore spreads
 * them evenly over a broken instance too. Least-connections is the classic repair, and it fails in a
 * different way — the least-loaded instance is the one everybody picks next, so its queue fills before
 * anyone notices, and a freshly started instance (zero connections) takes the whole world at once.
 *
 * <p>Power of two choices is the version with a proof behind it: pick two instances at random, keep the
 * better one. Because the choice is random, no instance is ever the unanimous favourite and no herd forms;
 * because it compares, the better of any pair is always taken. The maximum load is exponentially smaller
 * than the average-based alternative, and the cost is one extra random integer per request.
 *
 * <p><strong>The mistake is the important part.</strong> Choosing purely by score is a closed loop: an
 * instance measured badly once is never chosen again, so its number never changes, so it is never chosen.
 * The first version of this class measured exactly that — a stub's first exchange cost 167 ms because the
 * connection pool was cold, the other core answered in 116 ms, and the cold one received 1 request in 40
 * while its stale score kept it exiled. {@code exploreRate} breaks the loop: a small fraction of requests
 * ignore the scores and take a random instance, which is the only way stale memory can ever be corrected.
 * The default is 5% — one request in twenty pays a little so the other nineteen are not decided by a
 * number from an hour ago. The memory decays as well (see {@link InstanceStats}), because an instance that
 * has gone quiet should be re-measured rather than remembered forever.
 *
 * <p>"Better" is {@link InstanceStats#score}: the moving average of the latency this instance has actually
 * answered with, plus a penalty while it is failing, decayed toward neutral as the sample ages. That makes
 * the balancer's memory the same object the operator can read at {@code /edge/lb} — a strategy whose
 * decisions cannot be inspected is a strategy nobody can debug at three in the morning.
 */
public class P2cLoadBalancer implements ReactorServiceInstanceLoadBalancer {

    private static final Logger LOG = LoggerFactory.getLogger(P2cLoadBalancer.class);

    private final String serviceId;
    private final ObjectProvider<ServiceInstanceListSupplier> supplierProvider;
    private final InstanceStats stats;
    private final double exploreRate;

    public P2cLoadBalancer(
            Environment environment, LoadBalancerClientFactory clientFactory, InstanceStats stats) {
        this.serviceId = environment.getProperty(LoadBalancerClientFactory.PROPERTY_NAME);
        this.supplierProvider = clientFactory.getLazyProvider(serviceId, ServiceInstanceListSupplier.class);
        this.stats = stats;
        this.exploreRate = Double.parseDouble(environment.getProperty("edge.lb.explore-rate", "0.05"));
        LOG.info("p2c balancer created for service '{}' (explore rate {})", serviceId, exploreRate);
    }

    @Override
    public Mono<Response<ServiceInstance>> choose(Request request) {
        ServiceInstanceListSupplier supplier =
                supplierProvider.getIfAvailable(NoopServiceInstanceListSupplier::new);
        return supplier.get(request).next().map(instances -> pick(instances, stats, exploreRate));
    }

    /**
     * The decision itself, separated from the reactive plumbing so it can be tested as arithmetic rather
     * than through a running gateway: one list in, one instance out.
     *
     * @param exploreRate the fraction of draws that ignore the scores; 0 makes the choice purely greedy,
     *     which is what the unit tests assert with, and 1 makes it uniform.
     */
    static Response<ServiceInstance> pick(
            List<ServiceInstance> instances, InstanceStats stats, double exploreRate) {
        if (instances.isEmpty()) {
            return new EmptyResponse();
        }
        if (instances.size() == 1) {
            // Nothing to choose between, and no reason to make the caller pay for a random draw.
            return new DefaultResponse(instances.get(0));
        }
        ThreadLocalRandom random = ThreadLocalRandom.current();
        if (exploreRate > 0 && random.nextDouble() < exploreRate) {
            return new DefaultResponse(instances.get(random.nextInt(instances.size())));
        }
        int first = random.nextInt(instances.size());
        int second = random.nextInt(instances.size() - 1);
        // Drawing from n-1 and shifting past the first index gives two *distinct* instances without a
        // rejection loop: the naive `while (second == first) second = nextInt(n)` can spin, and a spin on
        // the request path is the one place it must not.
        if (second >= first) {
            second += 1;
        }
        ServiceInstance left = instances.get(first);
        ServiceInstance right = instances.get(second);
        double leftScore = stats.score(key(left));
        double rightScore = stats.score(key(right));
        // Ties go to the first draw. A deterministic tie-break would privilege one instance forever.
        return new DefaultResponse(leftScore <= rightScore ? left : right);
    }

    /** The same key the response path records under, so a measurement and a decision name one listener. */
    static String key(ServiceInstance instance) {
        return instance.getHost() + ":" + instance.getPort();
    }
}

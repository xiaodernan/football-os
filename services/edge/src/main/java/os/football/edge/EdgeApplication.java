package os.football.edge;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.loadbalancer.annotation.LoadBalancerClients;
import os.football.lb.P2cLoadBalancerConfiguration;

/**
 * The edge: one door in, traced, protected, and answering no football question of its own.
 *
 * <p>Every request that reaches the product's API arrives here first and is forwarded to the canonical
 * Python core unchanged except for one added header. The gateway owns routing, the trace id and the
 * circuit breaker; the core owns the figures. Nothing in this module may compute a number a club would
 * read, because the moment it does, the two answers can disagree.
 *
 * <p>{@code @LoadBalancerClients} names the policy for every {@code lb://} route the edge will ever have,
 * including ones added after this line. The configuration class lives in {@code os.football.lb} — outside
 * this application's scanned package — so it is instantiated per service by Spring Cloud rather than
 * globally by component scan; that placement is the difference between a policy and an accident.
 */
@SpringBootApplication
@LoadBalancerClients(defaultConfiguration = P2cLoadBalancerConfiguration.class)
public class EdgeApplication {

    public static void main(String[] args) {
        SpringApplication.run(EdgeApplication.class, args);
    }
}

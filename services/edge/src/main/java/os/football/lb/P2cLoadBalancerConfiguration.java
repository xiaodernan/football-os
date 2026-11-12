package os.football.lb;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.cloud.loadbalancer.core.ReactorServiceInstanceLoadBalancer;
import org.springframework.cloud.loadbalancer.support.LoadBalancerClientFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import os.football.edge.InstanceStats;

/**
 * The edge's load-balancing policy, in a package the component scan does not reach.
 *
 * <p>That last clause is the whole subtlety. A {@code @Configuration} class found by {@code
 * @SpringBootApplication}'s scan becomes a bean in the main context, where it would replace the default
 * balancer for every {@code lb://} route globally whether or not the service asked for it — and Spring
 * Cloud's own documentation warns about exactly this. Declared through {@code @LoadBalancerClients} and
 * living outside the scanned package, it is instantiated per service in the child context Spring Cloud
 * builds for that service, which is where a load-balancing policy belongs.
 *
 * <p>The switch defaults to on: one instance makes the choice free, and two instances make round robin's
 * blindness expensive. {@code edge.lb.strategy=round-robin} restores the stock balancer when an operator
 * wants the old behaviour, which is what makes this deployable rather than a leap of faith.
 */
@Configuration(proxyBeanMethods = false)
public class P2cLoadBalancerConfiguration {

    @Bean
    @ConditionalOnProperty(name = "edge.lb.strategy", havingValue = "p2c", matchIfMissing = true)
    public ReactorServiceInstanceLoadBalancer p2cLoadBalancer(
            Environment environment, LoadBalancerClientFactory clientFactory, InstanceStats stats) {
        return new P2cLoadBalancer(environment, clientFactory, stats);
    }
}

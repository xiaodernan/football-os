package os.football.edge;

import java.util.List;
import java.util.Map;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Which instances of a service would the load balancer choose from?
 *
 * <p>The breaker door answers "is the core being asked?"; this door answers "who would be asked?".
 * Both are read from the same discovery client the {@code lb://} route resolves through, so the answer
 * is the live view of the registry rather than a configuration file's intention. An unknown name reads
 * as zero instances with a 200: "nobody is registered" is an answer, not an error, and an operator
 * distinguishing a missing registration from an unreachable instance needs it.
 */
@RestController
public class InstancesController {

    private final DiscoveryClient discoveryClient;

    InstancesController(DiscoveryClient discoveryClient) {
        this.discoveryClient = discoveryClient;
    }

    @GetMapping("/edge/instances")
    public Map<String, Object> instances(@RequestParam(defaultValue = "football-core") String service) {
        List<Map<String, Object>> instances = discoveryClient.getInstances(service).stream()
                .map(InstancesController::describe)
                .toList();
        return Map.of("service", service, "count", instances.size(), "instances", instances);
    }

    private static Map<String, Object> describe(ServiceInstance instance) {
        return Map.of(
                "instanceId", instance.getInstanceId() == null ? "" : instance.getInstanceId(),
                "host", instance.getHost(),
                "port", instance.getPort(),
                "uri", instance.getUri().toString(),
                "secure", instance.isSecure());
    }
}

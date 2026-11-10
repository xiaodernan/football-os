package os.football.edge;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

/**
 * One door that says what the whole service plane is doing.
 *
 * <p>Phase 11 grew one door per concern: routes, limits, the breaker, instances, config. An operator
 * who wants the shape of the platform would otherwise have to know all five and stitch them together.
 * This door does that stitching — and it does it by <em>calling the very same methods</em> the five doors
 * call, not by retyping their predicates. Each block is therefore the same answer its own door gives,
 * and the test compares them byte for byte. Nothing here computes a football fact; the Python core stays
 * canonical, and this door only describes the shape of the way in.
 */
@RestController
public class PlaneController {

    public static final String PATH = "/edge/plane";

    private final RoutesController routes;
    private final LimitsController limits;
    private final BreakerController breaker;
    private final InstancesController instances;
    private final ConfigController config;

    public PlaneController(
            RoutesController routes,
            LimitsController limits,
            BreakerController breaker,
            InstancesController instances,
            ConfigController config) {
        this.routes = routes;
        this.limits = limits;
        this.breaker = breaker;
        this.instances = instances;
        this.config = config;
    }

    @GetMapping(PATH)
    public Mono<Map<String, Object>> plane() {
        return routes.routes().collectList().map((List<RoutesController.ResolvedRoute> resolved) -> {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("routes", resolved);
            body.put("limits", limits.limits());
            body.put("breaker", breaker.breaker());
            body.put("instances", instances.instances("football-core"));
            body.put("config", config.config());
            body.put("trace", Map.of(
                    "parent_header", W3cTraceContextFilter.TRACE_PARENT,
                    "state_header", W3cTraceContextFilter.TRACE_STATE,
                    "correlation_header", TraceIdFilter.TRACE_HEADER,
                    "note", "a valid caller parent is preserved; an absent or invalid one is minted at the gateway"));
            body.put("doors", Map.of(
                    "routes", "/edge/routes",
                    "limits", "/edge/limits",
                    "breaker", "/edge/breaker",
                    "instances", "/edge/instances?service=football-core",
                    "config", ConfigController.PATH,
                    "refresh", "/actuator/refresh"));
            body.put("formula", "each block is the same method its own door calls; the plane adds no figure of its own");
            return body;
        });
    }
}

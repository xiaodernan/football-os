package os.football.edge;

import java.util.List;
import org.springframework.cloud.gateway.route.RouteDefinition;
import reactor.core.publisher.Flux;
import org.springframework.cloud.gateway.route.RouteDefinitionLocator;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The route table, read from the running gateway rather than from the YAML beside it.
 *
 * <p>A configuration file says what someone intended; this door says what the gateway actually resolved.
 * The two can differ — a placeholder that resolved to a different host, a route the profile never loaded —
 * and when they do, the difference is the bug. It answers nothing about football, only about itself.
 */
@RestController
public class RoutesController {

    private final RouteDefinitionLocator locator;

    public RoutesController(RouteDefinitionLocator locator) {
        this.locator = locator;
    }

    /**
     * The table as a stream, never blocked: a gateway handler runs on the netty event loop, where
     * {@code block()} is an exception rather than a slowdown. The sort is applied to the stream so the
     * door answers in a stable order without pulling it into memory first.
     */
    @GetMapping("/edge/routes")
    public Flux<ResolvedRoute> routes() {
        return locator.getRouteDefinitions()
                .map(RoutesController::describe)
                .sort((left, right) -> left.id().compareTo(right.id()));
    }

    private static ResolvedRoute describe(RouteDefinition definition) {
        return new ResolvedRoute(
                definition.getId(),
                String.valueOf(definition.getUri()),
                definition.getPredicates().stream()
                        .map(predicate -> predicate.getName() + "=" + predicate.getArgs())
                        .toList(),
                definition.getFilters().stream()
                        .map(filter -> filter.getName() + "=" + filter.getArgs())
                        .toList());
    }

    /** One row of the table: id, resolved target, and the predicates and filters in force. */
    public record ResolvedRoute(String id, String uri, List<String> predicates, List<String> filters) {}
}

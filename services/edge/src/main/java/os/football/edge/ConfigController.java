package os.football.edge;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * What the gateway is running with, read from the live bean.
 *
 * <p>A config server is only useful if an operator can ask what the process actually believes. This
 * door reads the {@code @RefreshScope} bean, so calling it before and after {@code /actuator/refresh}
 * answers the question "did the change land?" from the running process rather than from the file.
 */
@RestController
public class ConfigController {

    public static final String PATH = "/edge/config";

    private final PlaneSettings settings;

    public ConfigController(PlaneSettings settings) {
        this.settings = settings;
    }

    @GetMapping(PATH)
    public Map<String, Object> config() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("notice", settings.notice());
        body.put("refresh_endpoint", "/actuator/refresh");
        body.put("formula", "GET /edge/config reads a @RefreshScope bean; POST /actuator/refresh rebuilds it from the current config");
        body.put("note", "the value is the running gateway's, not the file's; a config server that is down leaves the last value in force");
        return body;
    }
}

package os.football.edge;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.context.config.annotation.RefreshScope;
import org.springframework.stereotype.Component;

/**
 * A setting that can change while the process is running.
 *
 * <p>The config server (item 47) serves the edge's settings as reviewable files, but until now the
 * gateway only read them at boot: changing a value meant restarting the one door every caller uses.
 * {@code @RefreshScope} makes this bean be rebuilt after {@code POST /actuator/refresh}, so the new
 * value takes effect without a restart. Nothing here computes a football fact — it is the plane's own
 * configuration, and the canonical core is untouched.
 */
@Component
@RefreshScope
public class PlaneSettings {

    private final String notice;

    public PlaneSettings(@Value("${edge.plane.notice:the plane is up}") String notice) {
        this.notice = notice;
    }

    /** The live value, as the running gateway sees it now — not the value the jar was built with. */
    public String notice() {
        return notice;
    }
}

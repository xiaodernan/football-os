package os.football.worldcheck;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * FOOTBALL OS world-check. A plane citizen that fetches the Python core's world status on a
 * schedule and reports arithmetic only — never a football rule, never positioned as a judge of
 * players. Answers `/actuator/health` for the plane's own operator wiring, and `/world/check` for
 * humans reading it on a terminal.
 */
@SpringBootApplication
@EnableScheduling
public class WorldCheckApplication {
    public static void main(String[] args) {
        SpringApplication.run(WorldCheckApplication.class, args);
    }
}

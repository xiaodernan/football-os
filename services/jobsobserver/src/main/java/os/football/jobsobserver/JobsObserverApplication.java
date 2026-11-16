package os.football.jobsobserver;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * FOOTBALL OS jobs observer. The plane's arithmetic eye on the jobs broker: it joins the
 * `football_os:jobs` Redis Stream under its own consumer group, acks what it sees and counts it.
 * It has no power over jobs — the Python core's state machine remains the only writer of job state.
 * Answers `/actuator/health` for the plane's operator wiring and `/jobs/observer` for humans on
 * a terminal.
 */
@SpringBootApplication
@EnableScheduling
public class JobsObserverApplication {
    public static void main(String[] args) {
        SpringApplication.run(JobsObserverApplication.class, args);
    }
}

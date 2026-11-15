package os.football.worldcheck.world;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** Tick once every ${worldcheck.check.interval-seconds}; the first ticks fire after the start, not during. */
@Component
public class WorldCheckScheduler {

    private final WorldCheckOrchestrator orchestrator;

    public WorldCheckScheduler(WorldCheckOrchestrator orchestrator) {
        this.orchestrator = orchestrator;
    }

    @Scheduled(fixedDelayString = "#{${worldcheck.check.interval-seconds:300} * 1000}")
    public void probe() {
        orchestrator.now();
    }
}

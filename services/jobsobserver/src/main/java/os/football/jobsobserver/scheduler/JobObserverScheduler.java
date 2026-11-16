package os.football.jobsobserver.scheduler;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import os.football.jobsobserver.observer.JobsStreamObserver;

/**
 * One scheduler tick per configured interval. Boot cost is one Redis connection later;
 * the cadence is the poll's difference between "quiet" and "unavailable" — a failed tick
 * counts for the health line, not for the log stream.
 */
@Component
public class JobObserverScheduler {
    private final JobsStreamObserver observer;

    public JobObserverScheduler(JobsStreamObserver observer) {
        this.observer = observer;
    }

    @Scheduled(fixedDelayString = "${jobsobserver.poll.interval-ms:1000}", initialDelayString = "${jobsobserver.poll.initial-delay-ms:2500}")
    public void tick() {
        observer.poll();
    }
}

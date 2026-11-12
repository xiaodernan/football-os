package os.football.edge;

import reactor.core.publisher.Mono;

/**
 * Where the shared token buckets live, as the gateway sees them.
 *
 * <p>An interface rather than a direct dependency on Redis for one reason: the filter that uses it must be
 * testable without a Redis server, and the refusal path — the one an operator reads during an incident — must
 * be provable without one too. The production implementation is {@link RedisBucketStore}; a test supplies its
 * own.
 */
public interface BucketStore {

    /** The answer a store gives when it could not judge: the caller is admitted and the local bucket decides. */
    long[] DEGRADED = {-1L, 0L, 0L};

    /**
     * Take one token from {@code key}'s bucket.
     *
     * @return three numbers — allowed (1/0), remaining tokens, and the milliseconds until one more token
     *     exists when refused. {@link #DEGRADED} when the store cannot answer.
     */
    Mono<long[]> take(String key, int capacity, double refillPerSecond);
}

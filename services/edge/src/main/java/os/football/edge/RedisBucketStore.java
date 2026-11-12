package os.football.edge;

import java.util.List;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

/**
 * The shared tier: one Lua script, one server clock, one bucket per caller across every gateway replica.
 *
 * <p>Why a script and not {@code GET} then {@code SET}: the read-modify-write has to be one operation, or two
 * replicas interleave and both spend the last token. Why {@code TIME} inside the script: with two replicas,
 * a bucket stamped by the clock of whichever replica answered is a bucket whose refill rate depends on which
 * door the caller used — a caller alternating between replicas would be refilled twice as fast. The server's
 * clock is the only clock every replica agrees on.
 *
 * <p>The script is byte-for-byte the algorithm the Python core runs ({@code app/core/ratelimit.py}), because
 * a caller must not be able to tell which tier judged it: same burst, same refill, same retry arithmetic,
 * same headers. Any difference would only be visible as a limit that changes when traffic moves between the
 * edge and the core.
 *
 * <p>The bean exists only when {@code edge.rate-limit.distributed=true}. That default is off, and it is off
 * on purpose: a gateway that tries to reach a store it was not given, on every request, spends its timeout
 * budget proving a configuration mistake. A deployment that runs Redis turns it on and names the host.
 */
@Component
@ConditionalOnProperty(name = "edge.rate-limit.distributed", havingValue = "true")
public class RedisBucketStore implements BucketStore {

    private static final String LUA = """
            local capacity = tonumber(ARGV[1])
            local refill_per_ms = tonumber(ARGV[2])
            local cost = tonumber(ARGV[3])
            local clock = redis.call('TIME')
            local now_ms = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
            local state = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
            local tokens = tonumber(state[1])
            local stamped = tonumber(state[2])
            if tokens == nil or stamped == nil then
              tokens = capacity
              stamped = now_ms
            end
            local elapsed = now_ms - stamped
            if elapsed < 0 then elapsed = 0 end
            tokens = math.min(capacity, tokens + elapsed * refill_per_ms)
            local allowed = 0
            if tokens >= cost then
              tokens = tokens - cost
              allowed = 1
            end
            redis.call('HSET', KEYS[1], 'tokens', string.format('%.6f', tokens), 'ts', now_ms)
            local ttl = math.ceil(capacity / refill_per_ms) + 1000
            redis.call('PEXPIRE', KEYS[1], ttl)
            local retry_ms = 0
            if allowed == 0 then
              retry_ms = math.ceil((cost - tokens) / refill_per_ms)
            end
            return {allowed, math.floor(tokens), retry_ms}
            """;

    private final ReactiveStringRedisTemplate template;
    private final RedisScript<List> script = new DefaultRedisScript<>(LUA, List.class);

    public RedisBucketStore(ReactiveStringRedisTemplate template) {
        this.template = template;
    }

    @Override
    public Mono<long[]> take(String key, int capacity, double refillPerSecond) {
        return template.execute(
                        script,
                        List.of(key),
                        Integer.toString(capacity),
                        Double.toString(refillPerSecond / 1000.0),
                        "1")
                .next()
                .map(reply -> {
                    if (reply.size() != 3) {
                        return DEGRADED;
                    }
                    long allowed = number(reply.get(0));
                    if (allowed < 0) {
                        return DEGRADED;
                    }
                    return new long[] {allowed, number(reply.get(1)), number(reply.get(2))};
                });
    }

    /**
     * A Redis integer reply, however the serializer handed it over.
     *
     * <p>The template is a {@code ReactiveStringRedisTemplate}, so a Lua number comes back as a {@code String}
     * — but the reply type is only known at runtime, and a driver upgrade that returns {@code Long} instead
     * must not turn every request into a 500. A value that parses as neither is reported as {@code -1}, which
     * the caller reads as "the store could not judge" and answers with the local bucket.
     */
    private static long number(Object value) {
        if (value instanceof Number numeric) {
            return numeric.longValue();
        }
        if (value == null) {
            return -1L;
        }
        try {
            return Long.parseLong(value.toString());
        } catch (NumberFormatException notANumber) {
            return -1L;
        }
    }
}

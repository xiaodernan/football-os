package os.football.edge;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * The edge: one door in, traced, protected, and answering no football question of its own.
 *
 * <p>Every request that reaches the product's API arrives here first and is forwarded to the canonical
 * Python core unchanged except for one added header. The gateway owns routing, the trace id and the
 * circuit breaker; the core owns the figures. Nothing in this module may compute a number a club would
 * read, because the moment it does, the two answers can disagree.
 */
@SpringBootApplication
public class EdgeApplication {

    public static void main(String[] args) {
        SpringApplication.run(EdgeApplication.class, args);
    }
}

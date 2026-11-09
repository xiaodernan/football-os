package os.football.registry;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.netflix.eureka.server.EnableEurekaServer;

/**
 * The registry: the one table that says where a service is.
 *
 * <p>It answers no football question. Its only claims are "this name is at this address" and "this
 * service is still saying so", which is exactly what the Python core cannot say about itself once
 * there is more than one of it. The server registers itself last because it is the first node: a
 * registry that waits for a registry to tell it where it is never starts.
 */
@SpringBootApplication
@EnableEurekaServer
public class RegistryApplication {

    public static void main(String[] args) {
        SpringApplication.run(RegistryApplication.class, args);
    }
}

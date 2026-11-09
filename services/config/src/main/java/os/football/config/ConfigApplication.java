package os.football.config;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.config.server.EnableConfigServer;

/**
 * The config server: configuration as a directory of files in this repository.
 *
 * <p>The `native` profile is deliberate. A git-backed server would make every boot depend on a remote
 * and every configuration change a commit somewhere else; the native profile reads the classpath copy
 * packaged with this module, so the configuration a service runs with is the configuration in the diff.
 */
@SpringBootApplication
@EnableConfigServer
public class ConfigApplication {

    public static void main(String[] args) {
        SpringApplication.run(ConfigApplication.class, args);
    }
}

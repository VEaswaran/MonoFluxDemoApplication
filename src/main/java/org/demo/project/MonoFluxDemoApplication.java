package org.demo.project;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Main entry point for MonoFluxDemo application
 * This Spring WebFlux application demonstrates the difference between Mono and Flux
 */
@SpringBootApplication
public class MonoFluxDemoApplication {

    public static void main(String[] args) {
        SpringApplication.run(MonoFluxDemoApplication.class, args);
    }
}


package org.demo.project.controller;

import org.demo.project.model.Product;
import org.demo.project.service.ProductService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Flux;

import static org.mockito.Mockito.when;

/**
 * Test class for FluxController
 * Demonstrates testing reactive endpoints that return Flux
 */
@WebFluxTest(FluxController.class)
public class FluxControllerTest {

    @Autowired
    private WebTestClient webTestClient;

    @MockBean
    private ProductService productService;

    @Test
    void testGetAllProducts() {
        Product product1 = new Product(1, "Laptop", 999.99, 5);
        Product product2 = new Product(2, "Mouse", 29.99, 50);

        when(productService.getAllProducts())
                .thenReturn(Flux.just(product1, product2));

        webTestClient.get()
                .uri("/api/flux/products")
                .exchange()
                .expectStatus().isOk()
                .expectBodyList(Product.class)
                .hasSize(2);
    }

    @Test
    void testStreamAllProducts() {
        Product product1 = new Product(1, "Laptop", 999.99, 5);
        Product product2 = new Product(2, "Mouse", 29.99, 50);

        when(productService.getAllProducts())
                .thenReturn(Flux.just(product1, product2));

        webTestClient.get()
                .uri("/api/flux/products-stream")
                .exchange()
                .expectStatus().isOk();
    }

    @Test
    void testGetProductsByPrice() {
        Product product1 = new Product(2, "Mouse", 29.99, 50);
        Product product2 = new Product(3, "Keyboard", 79.99, 30);

        when(productService.getProductsByMaxPrice(100.0))
                .thenReturn(Flux.just(product1, product2));

        webTestClient.get()
                .uri("/api/flux/products-by-price?maxPrice=100")
                .exchange()
                .expectStatus().isOk()
                .expectBodyList(Product.class)
                .hasSize(2);
    }

    @Test
    void testGetProductNames() {
        when(productService.getProductNames())
                .thenReturn(Flux.just("Laptop", "Mouse", "Keyboard"));

        webTestClient.get()
                .uri("/api/flux/product-names")
                .exchange()
                .expectStatus().isOk()
                .expectBodyList(String.class)
                .hasSize(3);
    }
}


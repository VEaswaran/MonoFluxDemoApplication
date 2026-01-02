package org.demo.project.service;

import org.demo.project.model.Product;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import reactor.test.StepVerifier;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Test class for ProductService
 * Demonstrates testing Flux with Reactor's StepVerifier
 */
@SpringBootTest
public class ProductServiceTest {

    @Autowired
    private ProductService productService;

    @Test
    void testGetAllProductsReturnsMultipleProducts() {
        StepVerifier.create(productService.getAllProducts())
                .expectNextCount(5)
                .verifyComplete();
    }

    @Test
    void testGetProductsByMaxPriceFiltersCorrectly() {
        StepVerifier.create(productService.getProductsByMaxPrice(100.0))
                .assertNext(product -> assertTrue(product.getPrice() <= 100.0))
                .assertNext(product -> assertTrue(product.getPrice() <= 100.0))
                .verifyComplete();
    }

    @Test
    void testGetLowStockProductsFiltersCorrectly() {
        StepVerifier.create(productService.getLowStockProducts(20))
                .assertNext(product -> assertTrue(product.getQuantity() < 20))
                .verifyComplete();
    }

    @Test
    void testGetProductNamesReturnsProductNames() {
        StepVerifier.create(productService.getProductNames())
                .expectNextCount(5)
                .verifyComplete();
    }
}


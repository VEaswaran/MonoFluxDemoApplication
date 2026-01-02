package org.demo.project.service;

import org.demo.project.model.Product;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.util.Arrays;
import java.util.List;

/**
 * ProductService demonstrates the use of Flux
 * Flux is used when you need to return multiple values (0 to N elements)
 */
@Service
public class ProductService {

    private List<Product> products = Arrays.asList(
            new Product(1, "Laptop", 999.99, 5),
            new Product(2, "Mouse", 29.99, 50),
            new Product(3, "Keyboard", 79.99, 30),
            new Product(4, "Monitor", 299.99, 10),
            new Product(5, "Headphones", 149.99, 25)
    );

    /**
     * Retrieve all products
     * Returns a Flux that emits multiple Product objects
     *
     * Use case: Getting multiple records from database, streaming data, list of items
     */
    public Flux<Product> getAllProducts() {
        return Flux.fromIterable(products);
    }

    /**
     * Retrieve products with price filter
     * Demonstrates Flux filtering capability
     */
    public Flux<Product> getProductsByMaxPrice(Double maxPrice) {
        return Flux.fromIterable(products)
                .filter(product -> product.getPrice() <= maxPrice);
    }

    /**
     * Retrieve products with low stock (quantity < threshold)
     * Demonstrates Flux filtering and business logic
     */
    public Flux<Product> getLowStockProducts(Integer threshold) {
        return Flux.fromIterable(products)
                .filter(product -> product.getQuantity() < threshold);
    }

    /**
     * Generate products with transformation
     * Demonstrates Flux map operation
     */
    public Flux<String> getProductNames() {
        return Flux.fromIterable(products)
                .map(Product::getName);
    }
}


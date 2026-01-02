package org.demo.project.controller;

import org.demo.project.model.Product;
import org.demo.project.service.ProductService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

/**
 * FluxController demonstrates endpoints that return Flux
 * Flux returns multiple responses (0 to N elements)
 *
 * Endpoints in this controller are ideal for:
 * - Fetching multiple resources
 * - Streaming data
 * - Server-Sent Events (SSE)
 * - Paginated or filtered lists
 *
 * Note: When using MediaType.APPLICATION_NDJSON_VALUE or APPLICATION_STREAM_JSON_VALUE,
 * the response is streamed to the client as items are emitted, rather than buffering all items.
 */
@RestController
@RequestMapping("/api/flux")
public class FluxController {

    @Autowired
    private ProductService productService;

    /**
     * Endpoint that returns all products as a JSON array
     * Returns Flux but Jackson automatically collects it into an array
     *
     * Example: GET /api/flux/products
     * Response: [{"id": 1, "name": "Laptop", ...}, {"id": 2, ...}, ...]
     */
    @GetMapping("/products")
    public Flux<Product> getAllProducts() {
        return productService.getAllProducts();
    }

    /**
     * Endpoint that streams products as JSON Lines (NDJSON)
     * Each item is a complete JSON object on its own line
     * Perfect for streaming large datasets
     *
     * Example: GET /api/flux/products-stream
     * Response (streaming):
     * {"id":1,"name":"Laptop","price":999.99,"quantity":5}
     * {"id":2,"name":"Mouse","price":29.99,"quantity":50}
     * ...
     */
    @GetMapping(value = "/products-stream", produces = MediaType.APPLICATION_NDJSON_VALUE)
    public Flux<Product> streamAllProducts() {
        return productService.getAllProducts();
    }

    /**
     * Endpoint that returns products filtered by max price
     * Demonstrates Flux with parameters
     *
     * Example: GET /api/flux/products-by-price?maxPrice=100
     * Response: Products with price <= 100
     */
    @GetMapping("/products-by-price")
    public Flux<Product> getProductsByPrice(@RequestParam(defaultValue = "500") Double maxPrice) {
        return productService.getProductsByMaxPrice(maxPrice);
    }

    /**
     * Endpoint that streams products filtered by price (NDJSON format)
     * Better for large result sets as items are streamed one by one
     *
     * Example: GET /api/flux/products-by-price-stream?maxPrice=200
     */
    @GetMapping(value = "/products-by-price-stream", produces = MediaType.APPLICATION_NDJSON_VALUE)
    public Flux<Product> streamProductsByPrice(@RequestParam(defaultValue = "500") Double maxPrice) {
        return productService.getProductsByMaxPrice(maxPrice);
    }

    /**
     * Endpoint that returns low stock products
     * Demonstrates business logic filtering with Flux
     *
     * Example: GET /api/flux/low-stock?threshold=20
     * Response: Products with quantity < threshold
     */
    @GetMapping("/low-stock")
    public Flux<Product> getLowStockProducts(@RequestParam(defaultValue = "15") Integer threshold) {
        return productService.getLowStockProducts(threshold);
    }

    /**
     * Endpoint that returns only product names
     * Demonstrates Flux map transformation
     *
     * Example: GET /api/flux/product-names
     * Response: ["Laptop", "Mouse", "Keyboard", ...]
     */
    @GetMapping("/product-names")
    public Flux<String> getProductNames() {
        return productService.getProductNames();
    }

    /**
     * Endpoint that streams product names as plain text, one per line
     *
     * Example: GET /api/flux/product-names-stream
     * Response (streaming):
     * Laptop
     * Mouse
     * Keyboard
     * ...
     */
    @GetMapping(value = "/product-names-stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> streamProductNames() {
        return productService.getProductNames();
    }

    /**
     * Endpoint that demonstrates Flux error handling
     * Combines two Flux streams
     *
     * Example: GET /api/flux/products-combined
     * Response: All products combined from multiple sources
     */
    @GetMapping("/products-combined")
    public Flux<Product> getCombinedProducts() {
        return Flux.concat(
                productService.getProductsByMaxPrice(100.0),
                productService.getProductsByMaxPrice(500.0)
        ).distinct();
    }
}


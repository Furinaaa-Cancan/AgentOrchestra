"""Product CRUD module with in-memory storage."""

products = {}
_next_id = 1


def create_product(name, price, stock=0):
    """Create a product with auto-incrementing ID.

    Args:
        name: Product name.
        price: Product price (must be > 0).
        stock: Initial stock count (default 0).

    Returns:
        dict with id, name, price, stock.

    Raises:
        ValueError: If price <= 0.
    """
    global _next_id
    if price <= 0:
        raise ValueError("price must be greater than 0")
    product = {
        "id": _next_id,
        "name": name,
        "price": price,
        "stock": stock,
    }
    products[_next_id] = product
    _next_id += 1
    return product


def get_product(product_id):
    """Get a product by ID.

    Returns:
        Product dict or None if not found.
    """
    return products.get(product_id)


def list_products(min_price=None, max_price=None):
    """Return all products, optionally filtered by price range.

    Args:
        min_price: Minimum price (inclusive). None means no lower bound.
        max_price: Maximum price (inclusive). None means no upper bound.

    Returns:
        List of product dicts matching the criteria.
    """
    result = list(products.values())
    if min_price is not None:
        result = [p for p in result if p["price"] >= min_price]
    if max_price is not None:
        result = [p for p in result if p["price"] <= max_price]
    return result


def update_stock(product_id, delta):
    """Update product stock by delta (can be negative).

    Args:
        product_id: The product ID to update.
        delta: Amount to add to stock (negative to decrease).

    Returns:
        Updated product dict.

    Raises:
        KeyError: If product_id does not exist.
        ValueError: If resulting stock would be negative.
    """
    product = products.get(product_id)
    if product is None:
        raise KeyError(f"Product {product_id} not found")
    new_stock = product["stock"] + delta
    if new_stock < 0:
        raise ValueError("Stock cannot be negative")
    product["stock"] = new_stock
    return product

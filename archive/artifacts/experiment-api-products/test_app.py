"""Tests for Product CRUD module."""

import pytest
from app import create_product, get_product, list_products, update_stock, products


@pytest.fixture(autouse=True)
def reset_products():
    """Reset products store before each test."""
    import app
    app.products.clear()
    app._next_id = 1


class TestListProducts:
    def test_list_all_products(self):
        create_product("A", 10, stock=5)
        create_product("B", 20, stock=3)
        create_product("C", 30, stock=1)
        result = list_products()
        assert len(result) == 3

    def test_list_empty(self):
        assert list_products() == []

    def test_filter_min_price(self):
        create_product("Cheap", 5)
        create_product("Mid", 15)
        create_product("Expensive", 25)
        result = list_products(min_price=10)
        assert len(result) == 2
        assert all(p["price"] >= 10 for p in result)

    def test_filter_max_price(self):
        create_product("Cheap", 5)
        create_product("Mid", 15)
        create_product("Expensive", 25)
        result = list_products(max_price=20)
        assert len(result) == 2
        assert all(p["price"] <= 20 for p in result)

    def test_filter_price_range(self):
        create_product("A", 5)
        create_product("B", 15)
        create_product("C", 25)
        result = list_products(min_price=10, max_price=20)
        assert len(result) == 1
        assert result[0]["name"] == "B"

    def test_filter_no_match(self):
        create_product("A", 5)
        result = list_products(min_price=100, max_price=200)
        assert result == []


class TestUpdateStock:
    def test_increase_stock(self):
        create_product("A", 10, stock=5)
        result = update_stock(1, 10)
        assert result["stock"] == 15

    def test_decrease_stock(self):
        create_product("A", 10, stock=10)
        result = update_stock(1, -5)
        assert result["stock"] == 5

    def test_decrease_to_zero(self):
        create_product("A", 10, stock=5)
        result = update_stock(1, -5)
        assert result["stock"] == 0

    def test_negative_stock_raises(self):
        create_product("A", 10, stock=5)
        with pytest.raises(ValueError):
            update_stock(1, -9999)

    def test_nonexistent_product_raises(self):
        with pytest.raises(KeyError):
            update_stock(999, 10)

    def test_returns_updated_product(self):
        p = create_product("A", 10, stock=5)
        result = update_stock(1, 3)
        assert isinstance(result, dict)
        assert result["id"] == 1
        assert result["stock"] == 8

from __future__ import annotations

from datetime import date

from bizpilot.extensions import db
from bizpilot.models import Category, Product, Sale


def test_product_create_update_and_soft_delete(app, client, auth):
    auth.login()
    with app.app_context():
        category_id = db.session.scalar(
            db.select(Category.id).where(Category.name == "Shirts")
        )
    response = client.post(
        "/products/",
        json={
            "name": "New Shirt",
            "category_id": category_id,
            "purchase_price": 500,
            "selling_price": 900,
            "stock_quantity": 3,
            "reorder_level": 5,
            "max_stock_level": 20,
        },
    )
    assert response.status_code == 201
    product = response.get_json()["product"]
    assert product["stock_status"] == "low_stock"
    response = client.put(
        f"/products/{product['id']}",
        json={"stock_quantity": 12, "selling_price": 950},
    )
    assert response.status_code == 200
    assert response.get_json()["product"]["stock_status"] == "sufficient"
    response = client.delete(f"/products/{product['id']}")
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Product, product["id"]).is_active is False


def test_product_rejects_below_cost_price(app, client, auth):
    auth.login()
    with app.app_context():
        category_id = db.session.scalar(
            db.select(Category.id).where(Category.name == "Shirts")
        )
    response = client.post(
        "/products/",
        json={
            "name": "Bad Margin",
            "category_id": category_id,
            "purchase_price": 1000,
            "selling_price": 500,
        },
    )
    assert response.status_code == 400


def test_user_cannot_access_another_users_product(app, client, auth):
    auth.login()
    with app.app_context():
        product_id = db.session.scalar(
            db.select(Product.id).where(Product.sku == "OTHER-1")
        )
    assert client.get(f"/products/{product_id}").status_code == 404
    assert client.delete(f"/products/{product_id}").status_code == 404


def test_sale_atomically_decrements_and_delete_restores_stock(app, client, auth):
    auth.login()
    with app.app_context():
        product = db.session.scalar(db.select(Product).where(Product.sku == "TEST-SHIRT"))
        product_id, before = product.id, product.stock_quantity
    response = client.post(
        "/sales/",
        json={
            "customer_name": "Sale Test",
            "sale_date": date.today().isoformat(),
            "payment_method": "UPI",
            "discount_amount": 100,
            "items": [{"product_id": product_id, "quantity": 2}],
        },
    )
    assert response.status_code == 201
    sale = response.get_json()["sale"]
    with app.app_context():
        assert db.session.get(Product, product_id).stock_quantity == before - 2
    response = client.delete(f"/sales/{sale['id']}")
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Product, product_id).stock_quantity == before
        assert db.session.get(Sale, sale["id"]).is_active is False


def test_sale_rejects_insufficient_stock_without_partial_change(app, client, auth):
    auth.login()
    with app.app_context():
        product = db.session.scalar(db.select(Product).where(Product.sku == "TEST-LINEN"))
        product_id, before = product.id, product.stock_quantity
    response = client.post(
        "/sales/",
        json={"items": [{"product_id": product_id, "quantity": before + 1}]},
    )
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(Product, product_id).stock_quantity == before


def test_expense_and_feedback_crud(client, auth):
    auth.login()
    expense = client.post(
        "/expenses/",
        json={
            "category": "Marketing",
            "description": "Campaign",
            "amount": 1500,
            "expense_date": date.today().isoformat(),
            "is_recurring": False,
        },
    )
    assert expense.status_code == 201
    expense_id = expense.get_json()["expense"]["id"]
    assert client.put(f"/expenses/{expense_id}", json={"amount": 1600}).status_code == 200
    assert client.delete(f"/expenses/{expense_id}").status_code == 200

    feedback = client.post(
        "/feedback/",
        json={
            "customer_name": "Customer",
            "rating": 2,
            "feedback_text": "Needs a better fit.",
            "feedback_date": date.today().isoformat(),
        },
    )
    assert feedback.status_code == 201
    item = feedback.get_json()["feedback"]
    assert item["sentiment"] == "negative"
    updated = client.put(
        f"/feedback/{item['id']}",
        json={"is_resolved": True, "resolution_notes": "Exchange completed."},
    )
    assert updated.status_code == 200
    assert updated.get_json()["feedback"]["is_resolved"] is True


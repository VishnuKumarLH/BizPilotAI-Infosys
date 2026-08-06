from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from bizpilot import create_app
from bizpilot.extensions import db
from bizpilot.models import (
    Category,
    CustomerFeedback,
    Expense,
    Product,
    Sale,
    SaleItem,
    User,
)
from config import TestConfig


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        user = User(
            username="demo",
            email="demo@example.com",
            business_name="Demo Menswear",
            business_address="Madurai",
        )
        user.set_password("password123")
        other = User(username="other", email="other@example.com", business_name="Other")
        other.set_password("password123")
        db.session.add_all([user, other])
        db.session.flush()
        shirts = Category(user_id=user.id, name="Shirts", description="Shirts")
        accessories = Category(user_id=user.id, name="Accessories", description="Accessories")
        other_category = Category(user_id=other.id, name="Other", description="Other")
        db.session.add_all([shirts, accessories, other_category])
        db.session.flush()
        leader = Product(
            user_id=user.id,
            category_id=shirts.id,
            name="Cotton Formal Shirt",
            sku="TEST-SHIRT",
            size="L",
            color="White",
            fabric_type="Cotton",
            purchase_price=Decimal("600"),
            selling_price=Decimal("1200"),
            stock_quantity=12,
            reorder_level=5,
            max_stock_level=30,
        )
        slow = Product(
            user_id=user.id,
            category_id=accessories.id,
            name="Classic Tie",
            sku="TEST-TIE",
            size="Free",
            color="Navy",
            fabric_type="Silk Blend",
            purchase_price=Decimal("250"),
            selling_price=Decimal("600"),
            stock_quantity=20,
            reorder_level=5,
            max_stock_level=30,
        )
        low = Product(
            user_id=user.id,
            category_id=shirts.id,
            name="Linen Shirt",
            sku="TEST-LINEN",
            size="M",
            color="Beige",
            fabric_type="Linen",
            purchase_price=Decimal("500"),
            selling_price=Decimal("1000"),
            stock_quantity=2,
            reorder_level=5,
            max_stock_level=30,
        )
        foreign_product = Product(
            user_id=other.id,
            category_id=other_category.id,
            name="Foreign Product",
            sku="OTHER-1",
            purchase_price=Decimal("1"),
            selling_price=Decimal("2"),
            stock_quantity=10,
            reorder_level=2,
            max_stock_level=20,
        )
        db.session.add_all([leader, slow, low, foreign_product])
        db.session.flush()
        sale = Sale(
            user_id=user.id,
            invoice_number="INV-TEST-001",
            customer_name="Customer",
            sale_date=date.today(),
            total_amount=Decimal("2400"),
            discount_amount=Decimal("0"),
            final_amount=Decimal("2400"),
            payment_method="UPI",
        )
        db.session.add(sale)
        db.session.flush()
        db.session.add(
            SaleItem(
                sale_id=sale.id,
                product_id=leader.id,
                product_name=leader.name,
                quantity=2,
                unit_price=leader.selling_price,
                total_price=Decimal("2400"),
            )
        )
        db.session.add(
            Expense(
                user_id=user.id,
                category="Rent",
                description="Monthly rent",
                amount=Decimal("1000"),
                expense_date=date.today(),
                payment_method="UPI",
            )
        )
        db.session.add(
            CustomerFeedback(
                user_id=user.id,
                customer_name="Happy Customer",
                product_id=leader.id,
                rating=5,
                feedback_text="Excellent shirt.",
                sentiment="positive",
                feedback_date=date.today(),
            )
        )
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth(client):
    class AuthActions:
        def login(self, email="demo@example.com", password="password123"):
            return client.post(
                "/auth/login",
                json={"email": email, "password": password},
                headers={"Accept": "application/json"},
            )

        def logout(self):
            return client.get("/auth/logout", headers={"Accept": "application/json"})

    return AuthActions()


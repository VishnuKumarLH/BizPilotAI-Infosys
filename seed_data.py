"""Create a realistic, deterministic StyleHub demo dataset."""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from app import app
from bizpilot.extensions import db
from bizpilot.models import (
    AgentExecutionLog,
    BusinessInsight,
    Category,
    ChatMessage,
    ChatSession,
    CustomerFeedback,
    Expense,
    Product,
    Sale,
    SaleItem,
    User,
)
from bizpilot.routes.auth import DEFAULT_CATEGORIES


PRODUCTS = [
    ("Formal Shirts", "Premium Cotton Formal Shirt", "SH-FS-001", "L", "White", "Cotton", 850, 1499, 25, 10, 60),
    ("Formal Shirts", "Slim Fit Business Shirt", "SH-FS-002", "M", "Blue", "Cotton", 720, 1299, 8, 10, 50),
    ("Formal Shirts", "Classic Oxford Shirt", "SH-FS-003", "XL", "Grey", "Cotton", 780, 1399, 18, 8, 45),
    ("Casual Shirts", "Classic Linen Casual Shirt", "SH-CS-001", "L", "Beige", "Linen", 520, 999, 15, 10, 45),
    ("Casual Shirts", "Checked Weekend Shirt", "SH-CS-002", "M", "Olive", "Cotton", 480, 899, 22, 10, 55),
    ("Casual Shirts", "Mandarin Collar Shirt", "SH-CS-003", "XL", "Maroon", "Cotton", 610, 1099, 4, 8, 40),
    ("T-Shirts", "Printed Cotton T-Shirt", "SH-TS-001", "M", "Navy", "Cotton", 270, 599, 40, 15, 80),
    ("T-Shirts", "Premium Polo T-Shirt", "SH-TS-002", "L", "Black", "Cotton", 520, 999, 28, 12, 70),
    ("T-Shirts", "Athleisure Dry-Fit Tee", "SH-TS-003", "XL", "Red", "Polyester", 390, 749, 34, 15, 75),
    ("T-Shirts", "Essential Crew Neck Tee", "SH-TS-004", "S", "White", "Cotton", 210, 449, 30, 12, 70),
    ("Pants & Trousers", "Formal Trouser", "SH-PT-001", "32", "Black", "Polyester Blend", 980, 1799, 6, 10, 45),
    ("Pants & Trousers", "Slim Chino Trouser", "SH-PT-002", "34", "Khaki", "Cotton", 850, 1599, 19, 8, 45),
    ("Pants & Trousers", "Comfort Fit Track Pant", "SH-PT-003", "L", "Charcoal", "Cotton Blend", 430, 899, 26, 10, 60),
    ("Jeans", "Premium Denim Jeans", "SH-JN-001", "32", "Dark Blue", "Denim", 1450, 2499, 12, 8, 35),
    ("Jeans", "Stonewash Regular Jeans", "SH-JN-002", "34", "Light Blue", "Denim", 1050, 1999, 20, 8, 40),
    ("Jeans", "Black Slim Jeans", "SH-JN-003", "30", "Black", "Denim", 1180, 2199, 7, 8, 35),
    ("Traditional Wear", "Cotton Kurta Traditional", "SH-TW-001", "L", "White", "Cotton", 460, 899, 3, 8, 35),
    ("Traditional Wear", "Silk Blend Kurta", "SH-TW-002", "XL", "Maroon", "Silk Blend", 820, 1499, 0, 5, 25),
    ("Traditional Wear", "Classic Cotton Veshti", "SH-TW-003", "Free", "Cream", "Cotton", 380, 749, 16, 6, 30),
    ("Traditional Wear", "Festival Kurta Jacket Set", "SH-TW-004", "XXL", "Navy", "Silk Blend", 1550, 2899, 5, 5, 20),
    ("Accessories", "Leather Belt", "SH-AC-001", "Free", "Brown", "Leather", 220, 499, 20, 10, 50),
    ("Accessories", "Designer Tie Set", "SH-AC-002", "Free", "Blue", "Silk Blend", 310, 699, 18, 10, 45),
    ("Accessories", "Classic Bi-Fold Wallet", "SH-AC-003", "Free", "Black", "Leather", 420, 899, 11, 8, 35),
    ("Accessories", "Silver Cufflink Pair", "SH-AC-004", "Free", "Silver", "Metal", 340, 799, 24, 8, 40),
]


EXPENSES = [
    ("Rent", "Monthly showroom rent", 15000, "Bank Transfer", "Meenakshi Properties", True),
    ("Electricity", "Store electricity bill", 3500, "UPI", "TANGEDCO", True),
    ("Staff Salary", "Sales associate salary", 12000, "Bank Transfer", "Payroll", True),
    ("Staff Salary", "Inventory associate salary", 12000, "Bank Transfer", "Payroll", True),
    ("Marketing", "Social media campaign", 2000, "Card", "Local Media Co.", False),
    ("Supplies", "Carry bags and garment tags", 1500, "UPI", "Madurai Packs", False),
    ("Maintenance", "Air-conditioner service", 2000, "Cash", "CoolCare Services", False),
    ("Internet/Phone", "Broadband and business mobile", 1200, "UPI", "Telecom Provider", True),
    ("Transport/Delivery", "Local order deliveries", 1800, "Cash", "City Courier", False),
    ("Miscellaneous", "Cleaning and refreshments", 1000, "Cash", "Various", False),
    ("Fixtures", "Display rack repair", 2200, "UPI", "StoreCraft", False),
    ("Marketing", "Festival window posters", 1350, "Cash", "Print Hub", False),
]


FEEDBACK = [
    ("Arun Kumar", "SH-FS-001", 5, "Excellent fabric and a sharp fit for office meetings.", True, "Thanked customer."),
    ("Mohamed Rizwan", "SH-JN-001", 4, "Good quality denim and comfortable for long wear.", False, None),
    ("Karthik S", "SH-CS-001", 5, "The linen shirt feels very light in Madurai weather.", False, None),
    ("Suresh Babu", "SH-PT-001", 2, "The waist fit felt tighter than the marked size.", False, None),
    ("Vignesh R", "SH-TS-002", 4, "Polo colour and finish are premium.", True, "Shared care instructions."),
    ("Pradeep M", "SH-TW-002", 3, "Loved the design but my size was unavailable.", False, None),
    ("Ramesh N", "SH-AC-001", 5, "Strong belt and good value for money.", False, None),
    ("Ajay Raj", "SH-TS-003", 4, "Comfortable for workouts and dries quickly.", True, "Thanked customer."),
    ("Naveen P", "SH-JN-003", 2, "Black colour faded slightly after the first wash.", False, None),
    ("Dinesh K", "SH-TW-003", 5, "Comfortable veshti with a neat traditional look.", False, None),
]


def seed(reset: bool = False) -> None:
    rng = random.Random(42)
    db.create_all()
    user = db.session.scalar(db.select(User).where(User.email == "demo@stylehub.com"))
    if user and reset:
        _clear_demo(user)
        user = None
    if user and db.session.scalar(
        db.select(db.func.count(Product.id)).where(Product.user_id == user.id)
    ):
        print("Demo data already exists. Run `python seed_data.py --reset` to rebuild it.")
        return

    if not user:
        user = User(
            username="demo@stylehub.com",
            email="demo@stylehub.com",
            business_name="StyleHub Men's Fashion",
            business_type="Men's Clothing Retail",
            business_address="Madurai, Tamil Nadu",
            business_phone="+91 98765 43210",
        )
        user.set_password("demo123")
        db.session.add(user)
        db.session.flush()

    category_rows = {}
    for name, description in DEFAULT_CATEGORIES.items():
        category = Category(user_id=user.id, name=name, description=description)
        db.session.add(category)
        category_rows[name] = category
    db.session.flush()

    products = []
    for row in PRODUCTS:
        category_name, name, sku, size, color, fabric, cost, price, stock, reorder, maximum = row
        product = Product(
            user_id=user.id,
            category_id=category_rows[category_name].id,
            name=name,
            description=f"{color} {fabric.lower()} {name.lower()} for modern menswear.",
            sku=sku,
            size=size,
            color=color,
            fabric_type=fabric,
            purchase_price=Decimal(str(cost)),
            selling_price=Decimal(str(price)),
            stock_quantity=stock + 12,
            reorder_level=reorder,
            max_stock_level=maximum,
        )
        db.session.add(product)
        products.append(product)
    db.session.flush()

    customers = [
        "Arun Kumar", "Bala Murugan", "Charles J", "Deepak R", "Elango P",
        "Farooq A", "Ganesh S", "Hari Prasad", "Imran K", "Jeeva M",
        "Karthik S", "Lokesh V", "Manoj K", "Naveen P", "Pradeep M",
    ]
    payment_methods = ["Cash", "Card", "UPI"]
    for index in range(30):
        sale_date = date.today() - timedelta(days=rng.randint(0, 29))
        selected = rng.sample(products, rng.randint(1, 3))
        discount = Decimal(str(rng.choice([0, 0, 0, 50, 100, 150])))
        sale = Sale(
            user_id=user.id,
            invoice_number=f"INV-{sale_date.strftime('%Y%m%d')}-{index + 1:03d}",
            customer_name=rng.choice(customers),
            customer_phone=f"9{rng.randint(100000000, 999999999)}",
            sale_date=sale_date,
            sale_time=datetime.strptime(
                f"{rng.randint(10, 20)}:{rng.choice([0, 15, 30, 45]):02d}", "%H:%M"
            ).time(),
            total_amount=0,
            discount_amount=discount,
            final_amount=0,
            payment_method=rng.choice(payment_methods),
        )
        db.session.add(sale)
        db.session.flush()
        total = Decimal("0")
        for product in selected:
            quantity = rng.choice([1, 1, 1, 2])
            quantity = min(quantity, product.stock_quantity)
            line_total = product.selling_price * quantity
            product.stock_quantity -= quantity
            total += line_total
            db.session.add(
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    product_name=product.name,
                    quantity=quantity,
                    unit_price=product.selling_price,
                    total_price=line_total,
                )
            )
        sale.total_amount = total
        sale.discount_amount = min(discount, total)
        sale.final_amount = total - sale.discount_amount

    # Historical sales may have been followed by supplier deliveries. Keep the
    # current stock snapshot at the intentionally varied levels in PRODUCTS so
    # the demo includes healthy, low-stock, and out-of-stock decisions.
    target_stock_by_sku = {row[2]: row[8] for row in PRODUCTS}
    for product in products:
        product.stock_quantity = target_stock_by_sku[product.sku]

    for index, row in enumerate(EXPENSES):
        category, description, amount, payment, vendor, recurring = row
        db.session.add(
            Expense(
                user_id=user.id,
                category=category,
                description=description,
                amount=Decimal(str(amount)),
                expense_date=date.today() - timedelta(days=index * 2),
                payment_method=payment,
                vendor_name=vendor,
                bill_reference=f"BILL-{index + 1:03d}",
                is_recurring=recurring,
            )
        )

    by_sku = {product.sku: product for product in products}
    for index, row in enumerate(FEEDBACK):
        customer, sku, rating, text, resolved, notes = row
        db.session.add(
            CustomerFeedback(
                user_id=user.id,
                customer_name=customer,
                product_id=by_sku[sku].id,
                rating=rating,
                feedback_text=text,
                sentiment="positive" if rating >= 4 else "neutral" if rating == 3 else "negative",
                feedback_date=date.today() - timedelta(days=index * 3),
                is_resolved=resolved,
                resolution_notes=notes,
            )
        )
    db.session.commit()
    print("BizPilot AI demo data created successfully.")
    print("  Demo login: demo@stylehub.com / demo123")
    print(f"  Categories: {len(DEFAULT_CATEGORIES)}")
    print(f"  Products: {len(PRODUCTS)}")
    print("  Sales: 30")
    print(f"  Expenses: {len(EXPENSES)}")
    print(f"  Feedback: {len(FEEDBACK)}")


def _clear_demo(user: User) -> None:
    message_ids = db.session.scalars(
        db.select(ChatMessage.id).where(ChatMessage.user_id == user.id)
    ).all()
    if message_ids:
        db.session.execute(
            db.delete(AgentExecutionLog).where(
                AgentExecutionLog.message_id.in_(message_ids)
            )
        )
    for model in (
        ChatMessage,
        ChatSession,
        BusinessInsight,
        CustomerFeedback,
        Expense,
        SaleItem,
        Sale,
        Product,
        Category,
    ):
        if model is SaleItem:
            sale_ids = db.session.scalars(
                db.select(Sale.id).where(Sale.user_id == user.id)
            ).all()
            if sale_ids:
                db.session.execute(db.delete(SaleItem).where(SaleItem.sale_id.in_(sale_ids)))
        elif hasattr(model, "user_id"):
            db.session.execute(db.delete(model).where(model.user_id == user.id))
    db.session.delete(user)
    db.session.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="Replace only the existing demo user's data."
    )
    args = parser.parse_args()
    with app.app_context():
        seed(reset=args.reset)

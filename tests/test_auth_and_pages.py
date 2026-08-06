from __future__ import annotations

from bizpilot.extensions import db
from bizpilot.models import Category, User


def test_protected_page_redirects_to_login(client):
    response = client.get("/products/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_demo_login_and_all_pages_render(client, auth):
    assert auth.login().status_code == 200
    for path in (
        "/",
        "/products/",
        "/sales/",
        "/expenses/",
        "/feedback/",
        "/agent-history",
        "/memory",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert b"BizPilot" in response.data


def test_registration_hashes_password_and_creates_categories(app, client):
    response = client.post(
        "/auth/register",
        json={
            "username": "newowner",
            "email": "new@example.com",
            "password": "securepass",
            "confirm_password": "securepass",
            "business_name": "New Store",
        },
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 201
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "new@example.com"))
        assert user is not None
        assert user.password_hash != "securepass"
        assert user.check_password("securepass")
        count = db.session.scalar(
            db.select(db.func.count(Category.id)).where(Category.user_id == user.id)
        )
        assert count == 7


def test_duplicate_registration_is_rejected(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "demo",
            "email": "demo@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400

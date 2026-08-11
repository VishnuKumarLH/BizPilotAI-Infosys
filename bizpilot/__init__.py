"""BizPilot AI application factory."""

from __future__ import annotations

from flasgger import Swagger
from flask import Flask, jsonify, redirect, render_template, url_for

from config import Config
from .extensions import cache, db, login_manager, migrate
from .services.scheduler import init_scheduler, sync_templates_to_scheduler


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)
    Swagger(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    from .routes.agent import agent_bp
    from .routes.api.workflow_automation import workflow_automation_bp
    from .routes.auth import auth_bp
    from .routes.chat import chat_bp
    from .routes.dashboard import dashboard_bp
    from .routes.expenses import expenses_bp
    from .routes.feedback import feedback_bp
    from .routes.main import main_bp
    from .routes.products import products_bp
    from .routes.sales import sales_bp
    from .routes.tools import tools_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(workflow_automation_bp)
    app.register_blueprint(dashboard_bp)

    if not app.config.get("TESTING"):
        init_scheduler(app)

    @app.cli.command("sync-scheduler")
    def sync_scheduler_cmd():
        """Reload and synchronize scheduled jobs from WorkflowTemplate table."""
        sync_templates_to_scheduler(app)
        print("Successfully synchronized WorkflowTemplates with background scheduler.")

    @app.get("/favicon.ico")
    def favicon():
        return redirect(url_for("static", filename="images/bizpilot-ai-logo.png"))

    @app.errorhandler(404)
    def not_found(error):
        if _wants_json():
            return jsonify({"error": "The requested resource was not found."}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        if _wants_json():
            return jsonify({"error": "An unexpected error occurred."}), 500
        return render_template("errors/500.html"), 500

    return app



def _wants_json() -> bool:
    from flask import request

    return request.path.startswith(
        (
            "/api/",
            "/chat/",
            "/products/",
            "/sales/",
            "/expenses/",
            "/feedback/",
            "/tools/",
        )
    ) and request.accept_mimetypes.best == "application/json"

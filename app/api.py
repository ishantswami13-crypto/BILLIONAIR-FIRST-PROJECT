from flask import Flask, jsonify


def register_api(app: Flask):
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.merchant.routes import bp as merchant_bp
    from .blueprints.inventory.routes import bp as inventory_bp
    from .blueprints.sales.routes import bp as sales_bp
    from .blueprints.payments.routes import bp as payments_bp
    from .blueprints.expenses.routes import bp as expenses_bp
    from .blueprints.reports.routes import bp as reports_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(merchant_bp, url_prefix="/api/merchant")
    app.register_blueprint(inventory_bp, url_prefix="/api/inventory")
    app.register_blueprint(sales_bp, url_prefix="/api/sales")
    app.register_blueprint(payments_bp, url_prefix="/api/payments")
    app.register_blueprint(expenses_bp, url_prefix="/api/expenses")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")


def register_errors(app: Flask):
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad request"}), 400

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "server error"}), 500

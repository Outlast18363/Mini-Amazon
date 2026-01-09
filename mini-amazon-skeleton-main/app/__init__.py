from flask import Flask
from flask_login import LoginManager
from .config import Config
from .db import DB

login = LoginManager()
login.login_view = 'users.login'


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Attach DB helper
    app.db = DB(app)
    login.init_app(app)

    # -----------------------------
    # Blueprints
    # -----------------------------
    from .index import bp as index_bp
    app.register_blueprint(index_bp)

    from .users import bp as user_bp
    app.register_blueprint(user_bp)

    from .sellers import bp as sellers_bp
    app.register_blueprint(sellers_bp)


    from .products import bp as products_bp
    app.register_blueprint(products_bp)

    from .categories import bp as categories_bp
    app.register_blueprint(categories_bp)

    from .cart import bp as cart_bp
    app.register_blueprint(cart_bp)

    from .orders import bp as orders_bp
    app.register_blueprint(orders_bp)

    from .inventory import bp as inventory_bp
    app.register_blueprint(inventory_bp)

    from .reviews import bp as reviews_bp
    app.register_blueprint(reviews_bp)

    from .messages import bp as messages_bp
    app.register_blueprint(messages_bp)

    # -----------------------------
    # Context processor: expose seller flag + unread messages safely
    # -----------------------------
    from flask_login import current_user
    from .models.seller import Seller
    from .messages import get_unread_count

    @app.context_processor
    def inject_flags():
        is_seller = False
        unread_messages = 0

        if current_user.is_authenticated:
            # Resolve seller flag safely
            try:
                is_seller = Seller.is_user_seller(current_user.id)
            except Exception as e:
                print("ERROR in Seller.is_user_seller:", e)
                is_seller = False

            # Resolve unread messages safely
            try:
                unread_messages = get_unread_count(current_user.id)
            except Exception as e:
                print("ERROR in get_unread_count:", e)
                unread_messages = 0

        return {
            "is_seller": is_seller,
            "unread_messages": unread_messages
        }

    return app

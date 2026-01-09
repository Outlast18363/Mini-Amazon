from flask import render_template
from flask_login import current_user
import datetime

from .models.product import Product
from .models.seller import Seller
from .models.purchase import Purchase

from flask import Blueprint
bp = Blueprint('index', __name__)


@bp.route('/')
def index():
    # get all available products for sale:
    products = Product.get_all(True)
    # find the products current user has bought:
    if current_user.is_authenticated:
        purchases = Purchase.get_all_by_uid_since(
            current_user.id, datetime.datetime(1980, 9, 14, 0, 0, 0))
    else:
        purchases = None

    is_seller = False
    if current_user.is_authenticated:
        if Seller.is_user_seller(current_user.id):
            is_seller = True

    # render the page by adding information to the index.html file
    return render_template(
        'index.html',
        avail_products=products,
        purchase_history=purchases,
        is_seller=is_seller
)

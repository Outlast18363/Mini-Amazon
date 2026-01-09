from flask import Blueprint, redirect, url_for, flash
from flask_login import login_required, current_user

from .models.seller import Seller

bp = Blueprint('sellers', __name__)

@bp.route('/become_seller', methods=['POST'])
@login_required
def become_seller():
    if Seller.become_seller(current_user.id):
        flash("You are now a seller!", "success")
    else:
        flash("You are already a seller.", "info")
    return redirect(url_for('index.index'))


@bp.route('/remove_seller', methods=['POST'])
@login_required
def remove_seller():
    if Seller.remove_seller(current_user.id):
        flash("You are no longer a seller.", "success")
    else:
        flash("You are not a seller.", "info")
    return redirect(url_for('index.index'))

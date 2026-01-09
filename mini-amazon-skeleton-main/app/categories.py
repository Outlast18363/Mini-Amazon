from flask import Blueprint, render_template


bp = Blueprint('categories', __name__)


@bp.route('/categories')
def index():
    # TODO (Jameson): list categories for browsing
    return render_template('categories/index.html')



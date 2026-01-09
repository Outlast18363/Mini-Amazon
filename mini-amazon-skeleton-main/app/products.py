from flask import Blueprint, request, redirect, url_for, render_template
from flask_login import login_required, current_user

from .models.product import Product
from .models.category import Category
from .models.inventory import InventoryItem
from .models.product_review import ProductReview


bp = Blueprint('products', __name__)


@bp.route('/products')
def browse():
    category = request.args.get('category', type=str)
    search = request.args.get('search', type=str)
    sort = request.args.get('sort', type=str)
    limit = request.args.get('limit', type=int)
    page = request.args.get('page', 1, type=int)

    products = Product.search_filter_sort(
        category=category,
        search=search,
        sort=sort,
        limit=limit
    )

    total_products = len(products)
    PER_PAGE = 20 # fixed parameter for number of items per page
    total_pages = (total_products + PER_PAGE - 1) // PER_PAGE

    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    products = products[start:end]

    categories = Category.all()

    return render_template('products/browse.html', 
        products=products, 
        categories=categories,
        total_pages=total_pages,
        current_page=page,
    )


@bp.route('/products/<int:product_id>')
def detail(product_id: int):
    product = Product.get_verbose(product_id)
    if not product:
        return "Product not found", 404

    offers = InventoryItem.offers_for_product(product_id)
    reviews = ProductReview.for_product(product_id)
    return render_template(
        'products/detail.html', 
        product=product, 
        offers=offers,
        reviews=reviews
    )


@bp.route('/products/create', methods=['GET', 'POST'])
@login_required
def create():
    categories = Category.all()

    if request.method == 'GET':
        return render_template('products/create-edit.html', categories=categories, product=None)

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        image_url = request.form.get('image_url', None)
        category_id = request.form.get('category')
        if category_id == "":
            category_id = None
        else:
            category_id = int(category_id)
    
        product_id = Product.create(
            name=name,
            description=description,
            image_url=image_url,
            category_id=category_id,
            created_by=current_user.id
        )

        return redirect(url_for('products.detail', product_id=product_id))
    

@bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(product_id: int):
    categories = Category.all()
    product = Product.get_verbose(product_id)

    if not product:
        return "Product not found", 404

    if request.method == 'GET':
        return render_template('products/create-edit.html', categories=categories, product=product)

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        image_url = request.form.get('image_url', None)
        category_id = request.form.get('category')
        if category_id == "":
            category_id = None
        else:
            category_id = int(category_id)

        Product.update(
            product_id=product.id,
            name=name,
            description=description,
            image_url=image_url,
            category_id=category_id
        )

        return redirect(url_for('products.detail', product_id=product.id))

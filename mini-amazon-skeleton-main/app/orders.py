from flask import Blueprint, render_template, abort, current_app as app, jsonify
from flask_login import login_required, current_user

from .models.order import Order


bp = Blueprint('orders', __name__)


def _format_currency(cents: int) -> str:
    dollars = cents / 100 if cents else 0
    return f"${dollars:,.2f}"


@bp.route('/orders/<int:order_id>')
@login_required
def detail(order_id: int):
    order = Order.get(order_id, buyer_id=current_user.id)
    if not order:
        abort(404)

    rows = app.db.execute(
        '''
        SELECT
            oi.product_id,
            oi.seller_id,
            p.name AS product_name,
            p.description AS product_description,
            p.image_url AS product_image,
            u.full_name AS seller_name,
            oi.quantity,
            oi.unit_price_final_cents,
            oi.discount_cents,
            oi.fulfilled_at,
            pr.review_id AS existing_review_id,
            pr.rating AS existing_rating,
            pr.title AS existing_title,
            pr.body AS existing_body
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        JOIN sellers s ON s.id = oi.seller_id
        JOIN users u ON u.id = s.user_id
        LEFT JOIN product_reviews pr ON pr.product_id = oi.product_id 
            AND pr.author_user_id = :buyer_id
        WHERE oi.order_id = :order_id
        ORDER BY p.name
        ''',
        order_id=order_id,
        buyer_id=current_user.id,
    )

    items = []
    subtotal_cents = 0
    discount_cents = 0
    total_cents = 0
    all_fulfilled = True if rows else False

    for (
        product_id,
        seller_id,
        product_name,
        product_description,
        product_image,
        seller_name,
        quantity,
        unit_price_cents,
        per_unit_discount_cents,
        fulfilled_at,
        existing_review_id,
        existing_rating,
        existing_title,
        existing_body,
    ) in rows:
        effective_unit_cents = unit_price_cents - per_unit_discount_cents
        line_subtotal_cents = unit_price_cents * quantity
        line_discount_cents = per_unit_discount_cents * quantity
        line_total_cents = line_subtotal_cents - line_discount_cents

        subtotal_cents += line_subtotal_cents
        discount_cents += line_discount_cents
        total_cents += line_total_cents

        if fulfilled_at is None:
            all_fulfilled = False

        items.append(
            {
                "product_id": product_id,
                "seller_id": seller_id,
                "product_name": product_name,
                "seller_name": seller_name,
                "product_description": product_description,
                "product_image": product_image,
                "quantity": quantity,
                "unit_price_cents": unit_price_cents,
                "discount_cents": per_unit_discount_cents,
                "effective_unit_cents": effective_unit_cents,
                "line_total_cents": line_total_cents,
                "fulfilled_at": fulfilled_at,
                "has_review": existing_review_id is not None,
                "review_rating": existing_rating,
                "review_title": existing_title,
                "review_body": existing_body,
            }
        )

    totals = {
        "subtotal": _format_currency(subtotal_cents),
        "discount": _format_currency(discount_cents),
        "total": _format_currency(total_cents),
    }

    return render_template(
        "orders/detail.html",
        order=order,
        items=items,
        totals=totals,
        all_items_fulfilled=all_fulfilled,
        format_currency=_format_currency,
    )


@bp.get('/api/orders/seller/<int:seller_id>/any')
@login_required
def api_get_any_order_for_seller(seller_id: int):
    """Get any order ID for the current user that involves this seller"""
    row = app.db.query_one('''
        SELECT o.order_id
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.buyer_id = :buyer_id AND oi.seller_id = :seller_id
        LIMIT 1
    ''', buyer_id=current_user.id, seller_id=seller_id)
    
    if row:
        return jsonify({"ok": True, "order_id": row["order_id"]})
    else:
        return jsonify({"ok": False, "error": "No orders found"}), 404


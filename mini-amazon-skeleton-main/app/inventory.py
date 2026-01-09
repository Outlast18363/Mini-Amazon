# app/inventory.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from flask import current_app as app

bp = Blueprint('inventory', __name__)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def get_seller_id_for_current_user():
    """
    Return sellers.id for the logged-in user (or None if not a seller).
    Requires DB helper methods query_one/query_all/execute in app/db.py.
    """
    row = app.db.query_one(
        "SELECT id FROM sellers WHERE user_id = :uid",
        {"uid": current_user.id}
    )
    return row["id"] if row else None


# ------------------------------------------------------------
# Pages (HTML shells; the JS inside the templates calls the APIs below)
# ------------------------------------------------------------
@bp.route('/inventory')
@login_required
def manage():
    return render_template('inventory/manage.html')


@bp.route('/fulfillment')
@login_required
def fulfillment():
    return render_template('inventory/fulfillment.html')


@bp.route('/inventory/analytics')
@login_required
def inventory_analytics_page():
    """HTML shell for seller inventory analytics."""
    return render_template('inventory/analytics.html')


# ------------------------------------------------------------
# Inventory APIs
# ------------------------------------------------------------
@bp.get('/api/inventory')
@login_required
def api_inventory_list():
    """
    List the current seller's inventory with product info and basic ratings.

    Query params:
      - search: optional keyword for product name/description
      - sort: one of {name_asc, price_asc, price_desc, qty_desc, updated}
      - limit, offset: pagination

    Default sort: updated (most recently updated first).
    """
    seller_id = get_seller_id_for_current_user()
    if not seller_id:
        return jsonify({"error": "No seller record for this user"}), 403

    search = request.args.get("search")
    sort = (request.args.get("sort") or "updated").lower()
    limit = request.args.get("limit", type=int) or 100
    offset = request.args.get("offset", type=int) or 0

    sql = """
      SELECT
        i.seller_id,
        i.product_id,
        p.name AS product_name,
        p.description,
        p.image_url,
        i.price_cents,
        i.quantity_on_hand,
        i.updated_at,
        COALESCE(AVG(pr.rating), 0)::numeric(3,2) AS avg_rating,
        COUNT(pr.review_id) AS num_reviews
      FROM inventory i
      JOIN products p ON p.id = i.product_id
      LEFT JOIN product_reviews pr ON pr.product_id = p.id
      WHERE i.seller_id = :seller_id
        AND (
             :search IS NULL
             OR p.name ILIKE '%' || :search || '%'
             OR p.description ILIKE '%' || :search || '%'
        )
      GROUP BY i.seller_id, i.product_id, p.name, p.description, p.image_url,
               i.price_cents, i.quantity_on_hand, i.updated_at
      ORDER BY
        CASE WHEN :sort = 'price_desc' THEN i.price_cents END DESC,
        CASE WHEN :sort = 'price_asc'  THEN i.price_cents END ASC,
        CASE WHEN :sort = 'qty_desc'   THEN i.quantity_on_hand END DESC,
        CASE WHEN :sort = 'updated'    THEN i.updated_at END DESC,
        p.name ASC
      LIMIT :limit OFFSET :offset;
    """
    rows = app.db.query_all(sql, {
        "seller_id": seller_id,
        "search": search,
        "sort": sort,
        "limit": limit,
        "offset": offset
    })
    return jsonify({"seller_id": seller_id, "count": len(rows), "items": rows})



@bp.post('/api/inventory/upsert')
@login_required
def api_inventory_upsert():
    """
    Insert or update a product in the current seller's inventory.

    Body JSON: { "product_id": int, "price_cents": int or null, "quantity_on_hand": int or null }

    Behavior:

      NEW ITEM (no existing inventory row for this seller/product):
        - price_cents: if provided, use it; if missing/None, treat as 0.
        - quantity_on_hand: if provided, use it; if missing/None, treat as 0.
        - Insert row with those values.

      EXISTING ITEM (row already exists):
        - If only product_id is provided (price_cents and quantity_on_hand are None/missing):
            → Do nothing, return current row.
        - If only price_cents is provided:
            → Update price_cents, leave quantity_on_hand unchanged.
        - If only quantity_on_hand is provided:
            → Add the given quantity to existing quantity_on_hand (delta),
              keep price_cents unchanged.
        - If both price_cents and quantity_on_hand are provided:
            → Update price_cents,
              set quantity_on_hand = existing_quantity + given_quantity.
    """
    seller_id = get_seller_id_for_current_user()
    if not seller_id:
        return jsonify({"error": "No seller record for this user"}), 403

    data = request.get_json(silent=True) or {}

    pid_raw = data.get("product_id")
    price_raw = data.get("price_cents", None)
    qty_raw = data.get("quantity_on_hand", None)

    if pid_raw is None:
        return jsonify({"error": "product_id is required"}), 400

    try:
        pid = int(pid_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "product_id must be an integer"}), 400

    # Look up existing inventory row for this seller/product
    existing = app.db.query_one("""
        SELECT seller_id, product_id, price_cents, quantity_on_hand, updated_at
        FROM inventory
        WHERE seller_id = :sid AND product_id = :pid
    """, {"sid": seller_id, "pid": pid})

    # ------------------------------------------------------------
    # EXISTING ROW
    # ------------------------------------------------------------
    if existing:
        cur_price = existing["price_cents"]
        cur_qty = existing["quantity_on_hand"]

        # Normalize "field present but null" vs "truly missing" from the client
        # We treat both missing and explicit null as "no change" for existing rows.
        price_provided = ("price_cents" in data) and (price_raw is not None)
        qty_provided = ("quantity_on_hand" in data) and (qty_raw is not None)

        # Case: only product_id → change nothing
        if not price_provided and not qty_provided:
            return jsonify(existing), 200

        set_clauses = []
        params = {"sid": seller_id, "pid": pid}

        # If price is provided → update price
        if price_provided:
            try:
                new_price = int(price_raw)
            except (TypeError, ValueError):
                return jsonify({"error": "price_cents must be an integer"}), 400
            if new_price < 0:
                return jsonify({"error": "price_cents must be non-negative"}), 400
            if new_price != cur_price:
                set_clauses.append("price_cents = :price_cents")
                params["price_cents"] = new_price

        # If quantity is provided → add to existing quantity
        if qty_provided:
            try:
                delta_qty = int(qty_raw)
            except (TypeError, ValueError):
                return jsonify({"error": "quantity_on_hand must be an integer"}), 400
            if delta_qty < 0:
                return jsonify({"error": "quantity_on_hand must be non-negative"}), 400

            new_qty = cur_qty + delta_qty
            if new_qty != cur_qty:
                set_clauses.append("quantity_on_hand = :quantity_on_hand")
                params["quantity_on_hand"] = new_qty

        # If nothing actually changed, just return existing
        if not set_clauses:
            return jsonify(existing), 200

        row = app.db.query_one(f"""
          UPDATE inventory
             SET {', '.join(set_clauses)},
                 updated_at = now()
           WHERE seller_id = :sid AND product_id = :pid
           RETURNING seller_id, product_id, price_cents, quantity_on_hand, updated_at;
        """, params)
        return jsonify(row), 200

    # ------------------------------------------------------------
    # NEW ROW
    # ------------------------------------------------------------
    # For new items: treat missing/None as zero
    try:
        new_price = int(price_raw) if price_raw is not None else 0
    except (TypeError, ValueError):
        return jsonify({"error": "price_cents must be an integer if provided"}), 400

    try:
        new_qty = int(qty_raw) if qty_raw is not None else 0
    except (TypeError, ValueError):
        return jsonify({"error": "quantity_on_hand must be an integer if provided"}), 400

    if new_price < 0 or new_qty < 0:
        return jsonify({"error": "price_cents and quantity_on_hand must be non-negative"}), 400

    row = app.db.query_one("""
      INSERT INTO inventory (seller_id, product_id, price_cents, quantity_on_hand, updated_at)
      VALUES (:sid, :pid, :price_cents, :quantity_on_hand, now())
      RETURNING seller_id, product_id, price_cents, quantity_on_hand, updated_at;
    """, {
        "sid": seller_id,
        "pid": pid,
        "price_cents": new_price,
        "quantity_on_hand": new_qty
    })
    return jsonify(row), 201


@bp.patch('/api/inventory/<int:product_id>')
@login_required
def api_inventory_patch(product_id: int):
    """
    Update price and/or quantity for a product in the current seller's inventory.

    Body JSON (any subset): { "price_cents": int, "quantity_on_hand": int }

    This endpoint is used by the table's "Edit" button.
    """
    seller_id = get_seller_id_for_current_user()
    if not seller_id:
        return jsonify({"error": "No seller record for this user"}), 403

    data = request.get_json(silent=True) or {}
    sets, params = [], {"sid": seller_id, "pid": product_id}

    if "price_cents" in data:
        try:
            price = int(data["price_cents"])
        except (TypeError, ValueError):
            return jsonify({"error": "price_cents must be an integer"}), 400
        if price < 0:
            return jsonify({"error": "price_cents must be non-negative"}), 400
        params["price"] = price
        sets.append("price_cents = :price")

    if "quantity_on_hand" in data:
        try:
            qty = int(data["quantity_on_hand"])
        except (TypeError, ValueError):
            return jsonify({"error": "quantity_on_hand must be an integer"}), 400
        if qty < 0:
            return jsonify({"error": "quantity_on_hand must be non-negative"}), 400
        params["qty"] = qty
        sets.append("quantity_on_hand = :qty")

    if not sets:
        return jsonify({"error": "No fields to update"}), 400

    row = app.db.query_one(f"""
      UPDATE inventory
         SET {', '.join(sets)}, updated_at = now()
       WHERE seller_id = :sid AND product_id = :pid
       RETURNING seller_id, product_id, price_cents, quantity_on_hand, updated_at;
    """, params)

    if not row:
        return jsonify({"error": "inventory row not found"}), 404
    return jsonify(row)


@bp.delete('/api/inventory/<int:product_id>')
@login_required
def api_inventory_delete(product_id: int):
    """Remove a product from the current seller's inventory."""
    seller_id = get_seller_id_for_current_user()
    if not seller_id:
        return jsonify({"error": "No seller record for this user"}), 403

    app.db.execute(
        "DELETE FROM inventory WHERE seller_id = :sid AND product_id = :pid",
        sid=seller_id, pid=product_id
    )
    return jsonify({"ok": True})


# ------------------------------------------------------------
# Fulfillment APIs
# ------------------------------------------------------------
@bp.get('/api/fulfillment')
@login_required
def api_fulfillment_list():
    """
    List order line items for this seller.

    Query param:
      - status: 'PLACED' (unfulfilled) or 'FULFILLED' (default: PLACED)
    """
    seller_id = get_seller_id_for_current_user()
    if not seller_id:
        return jsonify({"error": "No seller record for this user"}), 403

    status = (request.args.get("status") or "PLACED").upper()
    want_unfulfilled = (status == "PLACED")

    rows = app.db.query_all("""
      SELECT
        oi.order_id,
        oi.product_id,
        p.name AS product_name,
        oi.quantity,
        oi.unit_price_final_cents,
        oi.discount_cents,
        oi.fulfilled_at,
        o.buyer_id,
        u.full_name AS buyer_name,
        u.address   AS buyer_address,
        o.placed_at
      FROM order_items oi
      JOIN orders o ON o.order_id = oi.order_id
      JOIN users  u ON u.id = o.buyer_id
      JOIN products p ON p.id = oi.product_id
      WHERE oi.seller_id = :sid
        AND (
              (:want)::boolean = TRUE  AND oi.fulfilled_at IS NULL
           OR (:want)::boolean = FALSE AND oi.fulfilled_at IS NOT NULL
        )
      ORDER BY
        CASE
          WHEN (:want)::boolean = FALSE THEN oi.fulfilled_at
          ELSE o.placed_at
        END DESC,
        oi.order_id DESC;
    """, {"sid": seller_id, "want": want_unfulfilled})
    return jsonify({"seller_id": seller_id, "count": len(rows), "items": rows})


@bp.post('/api/fulfillment/mark')
@login_required
def api_fulfillment_mark():
    """
    Mark one order line item as fulfilled (sets fulfilled_at = now()).

    Body JSON: { "order_id": int, "product_id": int }
    """
    seller_id = get_seller_id_for_current_user()
    if not seller_id:
        return jsonify({"error": "No seller record for this user"}), 403

    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    product_id = data.get("product_id")
    if order_id is None or product_id is None:
        return jsonify({"error": "order_id and product_id required"}), 400

    row = app.db.query_one("""
      UPDATE order_items
         SET fulfilled_at = COALESCE(fulfilled_at, now())
       WHERE order_id = :oid AND product_id = :pid AND seller_id = :sid
       RETURNING order_id, product_id, seller_id, fulfilled_at;
    """, {"oid": order_id, "pid": product_id, "sid": seller_id})

    if not row:
        return jsonify({"error": "line item not found"}), 404

    # Order status roll-up is handled by triggers in create.sql.
    return jsonify({"ok": True, "item": row})


# ------------------------------------------------------------
# Inventory Analytics APIs (Advanced Feature)
# ------------------------------------------------------------
@bp.get('/api/inventory/analytics')
@login_required
def api_inventory_analytics():
    """
    Return analytics for the current seller's inventory:
      - low_inventory: items with quantity_on_hand <= threshold
      - top_products: best-selling products over a recent window

    Query params:
      - threshold (int, default 5)
      - top_n (int, default 5)
      - window_days (int, default 90)
    """
    seller_id = get_seller_id_for_current_user()
    if not seller_id:
        return jsonify({"error": "No seller record for this user"}), 403

    threshold = request.args.get("threshold", type=int) or 5
    top_n = request.args.get("top_n", type=int) or 5
    window_days = request.args.get("window_days", type=int) or 90

    # --- Low inventory items for this seller ---
    low_sql = """
      SELECT
        i.product_id,
        p.name AS product_name,
        i.quantity_on_hand,
        i.price_cents,
        i.updated_at
      FROM inventory i
      JOIN products p ON p.id = i.product_id
      WHERE i.seller_id = :sid
        AND i.quantity_on_hand <= :threshold
      ORDER BY i.quantity_on_hand ASC, p.name ASC
      LIMIT 100
    """
    low_rows = app.db.query_all(low_sql, {
        "sid": seller_id,
        "threshold": threshold
    })

    # --- Top products (units sold and revenue) for this seller ---
    top_sql = """
      SELECT
        oi.product_id,
        p.name AS product_name,
        SUM(oi.quantity) AS total_units_sold,
        SUM( (oi.unit_price_final_cents - oi.discount_cents) * oi.quantity ) AS gross_revenue_cents,
        MIN(o.placed_at) AS first_sold_at,
        MAX(o.placed_at) AS last_sold_at
      FROM order_items oi
      JOIN orders o   ON o.order_id = oi.order_id
      JOIN products p ON p.id = oi.product_id
      WHERE oi.seller_id = :sid
        AND o.placed_at >= now() - (:window_days * INTERVAL '1 day')
      GROUP BY oi.product_id, p.name
      ORDER BY gross_revenue_cents DESC NULLS LAST, total_units_sold DESC
      LIMIT :top_n
    """
    top_rows = app.db.query_all(top_sql, {
        "sid": seller_id,
        "window_days": window_days,
        "top_n": top_n
    })

    return jsonify({
        "seller_id": seller_id,
        "params": {
            "threshold": threshold,
            "top_n": top_n,
            "window_days": window_days
        },
        "low_inventory": low_rows,
        "top_products": top_rows
    })

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from flask import current_app as app
from better_profanity import profanity

profanity.load_censor_words()
profanity.add_censor_words(['zebra'])

bp = Blueprint('reviews', __name__)


@bp.route('/reviews')
@login_required
def mine():
    product_reviews = app.db.query_all('''
        SELECT pr.review_id, pr.product_id, pr.rating, pr.title, pr.body, pr.updated_at,
               p.name AS product_name,
               COALESCE(COUNT(rhv.voter_user_id), 0) AS helpful_count
        FROM product_reviews pr
        JOIN products p ON p.id = pr.product_id
        LEFT JOIN review_helpful_votes rhv ON rhv.review_id = pr.review_id
        WHERE pr.author_user_id = :uid
        GROUP BY pr.review_id, pr.product_id, pr.rating, pr.title, pr.body, pr.updated_at, p.name
        ORDER BY pr.updated_at DESC
    ''', uid=current_user.id)
    
    seller_reviews = app.db.query_all('''
        SELECT sr.review_id, sr.seller_user_id, sr.rating, sr.title, sr.body, sr.updated_at,
               u.full_name AS seller_name, u.id AS seller_profile_user_id
        FROM seller_reviews sr
        JOIN sellers s ON s.id = sr.seller_user_id
        JOIN users u ON u.id = s.user_id
        WHERE sr.author_user_id = :uid
        ORDER BY sr.updated_at DESC
    ''', uid=current_user.id)
    
    purchasables = app.db.query_all("""
        SELECT DISTINCT ON (oi.product_id, oi.seller_id)
            oi.product_id,
            p.name AS product_name,
            oi.seller_id AS seller_user_id,
            u.full_name AS seller_name,
            u.id AS seller_profile_user_id,
            o.placed_at
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        JOIN products p ON p.id = oi.product_id
        JOIN sellers s ON s.id = oi.seller_id
        JOIN users   u ON u.id = s.user_id
        LEFT JOIN product_reviews pr ON pr.product_id = oi.product_id 
            AND pr.author_user_id = :uid
        WHERE o.buyer_id = :uid
          AND oi.fulfilled_at IS NOT NULL
          AND pr.review_id IS NULL
        ORDER BY oi.product_id, oi.seller_id, o.placed_at DESC
        LIMIT 20
    """, uid=current_user.id)
    
    return render_template('reviews/mine.html',
                           product_reviews=product_reviews,
                           seller_reviews=seller_reviews,
                           purchasables=purchasables)


# API Endpoints

@bp.post("/api/reviews/product/<int:product_id>")
@login_required
def api_upsert_product_review(product_id: int):
    data = request.get_json(silent=True) or {}
    rating = int(data.get("rating", 0))
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()

    # Check for profanity in title (if provided) and body
    if title and profanity.contains_profanity(title):
        return jsonify({"ok": False, "error": "Your review title contains inappropriate language. Please revise your review."}), 400
    if profanity.contains_profanity(body):
        return jsonify({"ok": False, "error": "Your review contains inappropriate language. Please revise your review."}), 400

    row = app.db.query_one("""
        INSERT INTO product_reviews(product_id, author_user_id, rating, title, body)
        VALUES (:pid, :uid, :rating, :title, :body)
        ON CONFLICT (author_user_id, product_id)
        DO UPDATE SET rating=EXCLUDED.rating,
                      title=EXCLUDED.title,
                      body=EXCLUDED.body,
                      updated_at=now()
        RETURNING review_id, rating, title, body, updated_at
    """, pid=product_id, uid=current_user.id, rating=rating, title=title, body=body)

    return jsonify({"ok": True, "review": row}), 200


@bp.post("/api/reviews/seller/<int:seller_id>")
@login_required
def api_upsert_seller_review(seller_id: int):
    data = request.get_json(silent=True) or {}
    rating = int(data.get("rating", 0))
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()

    if title and profanity.contains_profanity(title):
        return jsonify({"ok": False, "error": "Your review title contains inappropriate language. Please revise your review."}), 400
    if profanity.contains_profanity(body):
        return jsonify({"ok": False, "error": "Your review contains inappropriate language. Please revise your review."}), 400

    ok = app.db.query_one("""
        SELECT 1
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.buyer_id = :uid 
          AND oi.seller_id = :sid
          AND oi.fulfilled_at IS NOT NULL
        LIMIT 1
    """, uid=current_user.id, sid=seller_id)
    if not ok:
        return jsonify({"ok": False, "error": "need prior purchase from seller"}), 400

    row = app.db.query_one("""
        INSERT INTO seller_reviews(seller_user_id, author_user_id, rating, title, body)
        VALUES (:sid, :uid, :rating, :title, :body)
        ON CONFLICT (author_user_id, seller_user_id)
        DO UPDATE SET rating=EXCLUDED.rating,
                      title=EXCLUDED.title,
                      body=EXCLUDED.body,
                      updated_at=now()
        RETURNING review_id, rating, title, body, updated_at
    """, sid=seller_id, uid=current_user.id, rating=rating, title=title, body=body)

    return jsonify({"ok": True, "review": row}), 200


@bp.post("/api/reviews/<int:review_id>/helpful")
@login_required
def api_toggle_helpful(review_id: int):
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").lower()

    if action == "remove":
        app.db.execute("""
            DELETE FROM review_helpful_votes
            WHERE review_id = :rid AND voter_user_id = :uid
        """, rid=review_id, uid=current_user.id)
    else:
        app.db.execute("""
            INSERT INTO review_helpful_votes(review_id, voter_user_id)
            VALUES (:rid, :uid)
            ON CONFLICT DO NOTHING
        """, rid=review_id, uid=current_user.id)
    return jsonify({"ok": True}), 200


@bp.post("/api/reviews/product/<int:product_id>/delete")
@login_required
def api_delete_product_review(product_id: int):
    n = app.db.execute("""
        DELETE FROM product_reviews
        WHERE product_id = :pid AND author_user_id = :uid
    """, pid=product_id, uid=current_user.id)
    return jsonify({"ok": True, "deleted": n}), 200


@bp.post("/api/reviews/seller/<int:seller_id>/delete")
@login_required
def api_delete_seller_review(seller_id: int):
    n = app.db.execute("""
        DELETE FROM seller_reviews
        WHERE seller_user_id = :sid AND author_user_id = :uid
    """, sid=seller_id, uid=current_user.id)
    return jsonify({"ok": True, "deleted": n}), 200


@bp.get("/api/reviews/product/<int:product_id>")
def api_list_product_reviews(product_id: int):
    sort = (request.args.get("sort") or "new").lower()
    order_clause = "r.created_at DESC" if sort != "helpful" else "helpful_count DESC, r.created_at DESC"
    limit = max(min(int(request.args.get("limit", 10)), 50), 1)
    offset = max(int(request.args.get("offset", 0)), 0)

    rows = app.db.query_all(f"""
        SELECT r.review_id, r.author_user_id, r.rating, r.title, r.body, r.created_at,
               COALESCE(h.cnt, 0)::int AS helpful_count
        FROM product_reviews r
        LEFT JOIN (
          SELECT review_id, COUNT(*)::int AS cnt
          FROM review_helpful_votes
          GROUP BY review_id
        ) h USING(review_id)
        WHERE r.product_id = :pid
        ORDER BY {order_clause}
        LIMIT :lim OFFSET :off
    """, pid=product_id, lim=limit, off=offset)
    return jsonify({"ok": True, "items": rows}), 200

# Seller Public Profile

@bp.get("/sellers/<int:seller_id>")
def seller_public(seller_id: int):
    # Redirect to the new public profile page
    # We need to find the user_id associated with this seller_id
    row = app.db.execute("""
        SELECT user_id FROM sellers WHERE id = :sid
    """, sid=seller_id)
    
    if not row:
        return "Seller not found", 404
        
    user_id = row[0][0]
    return redirect(url_for('users.public_profile', user_id=user_id))

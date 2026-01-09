from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from flask import current_app as app
from better_profanity import profanity

bp = Blueprint('messages', __name__)

profanity.load_censor_words()
profanity.add_censor_words(['zebra'])


def get_unread_count(user_id: int) -> int:
    """Get count of unread messages for a user (either as buyer or seller)."""
    my_seller = app.db.query_one("SELECT id FROM sellers WHERE user_id = :uid", uid=user_id)
    my_sid = my_seller["id"] if my_seller else None
    
    # Count messages where:
    # - User is the buyer and sender is not the buyer (seller sent it)
    # - OR user is the seller and sender is not the seller (buyer sent it)
    # - AND message is unread (read_at IS NULL)
    result = app.db.query_one("""
        SELECT COUNT(*) as count
        FROM messages m
        JOIN message_threads mt ON mt.thread_id = m.thread_id
        WHERE m.read_at IS NULL
          AND m.sender_user_id != :uid
          AND (
            mt.buyer_user_id = :uid
            OR (:sid IS NOT NULL AND mt.seller_user_id = :sid)
          )
    """, uid=user_id, sid=my_sid)
    
    return result['count'] if result else 0

@bp.route('/messages')
@login_required
def threads():
    # threads where I'm buyer or I'm seller
    me = current_user.id
    my_seller = app.db.query_one("SELECT id FROM sellers WHERE user_id = :uid", uid=me)
    my_sid = my_seller["id"] if my_seller else None

    rows = app.db.query_all("""
      SELECT
        mt.thread_id, mt.order_id, mt.created_at,
        mt.buyer_user_id,
        mt.seller_user_id,
        s.user_id      AS seller_account_id,
        bu.full_name   AS buyer_name,
        su.full_name   AS seller_name,
        lm.body        AS last_body,
        lm.sent_at     AS last_sent_at,
        (SELECT COUNT(*) 
         FROM messages m 
         WHERE m.thread_id = mt.thread_id 
           AND m.sender_user_id != :uid 
           AND m.read_at IS NULL) AS unread_count
      FROM message_threads mt
      JOIN users bu     ON bu.id = mt.buyer_user_id
      JOIN sellers s    ON s.id = mt.seller_user_id
      JOIN users su     ON su.id = s.user_id
      LEFT JOIN LATERAL (
        SELECT body, sent_at
        FROM messages m
        WHERE m.thread_id = mt.thread_id
        ORDER BY sent_at DESC
        LIMIT 1
      ) lm ON true
      WHERE mt.buyer_user_id = :uid
         OR (:sid IS NOT NULL AND mt.seller_user_id = :sid)
      ORDER BY COALESCE(lm.sent_at, mt.created_at) DESC
    """, uid=me, sid=my_sid)

    return render_template('messages/threads.html', threads=rows)


@bp.route('/messages/<int:thread_id>')
@login_required
def thread(thread_id: int):
    # access check: buyer or seller account on thread
    z = app.db.query_one("""
      SELECT mt.buyer_user_id,
             s.user_id AS seller_user_account,
             mt.order_id,
             bu.full_name AS buyer_name,
             su.full_name AS seller_name
      FROM message_threads mt
      JOIN sellers s ON s.id = mt.seller_user_id
      JOIN users bu  ON bu.id = mt.buyer_user_id
      JOIN users su  ON su.id = s.user_id
      WHERE mt.thread_id = :tid
    """, tid=thread_id)
    if not z or current_user.id not in (z["buyer_user_id"], z["seller_user_account"]):
        return "Not allowed", 403

    # Mark messages as read (messages sent by the other party)
    app.db.execute("""
        UPDATE messages
        SET read_at = now()
        WHERE thread_id = :tid
          AND sender_user_id != :uid
          AND read_at IS NULL
    """, tid=thread_id, uid=current_user.id)

    msgs = app.db.query_all("""
      SELECT message_id, sender_user_id, body, sent_at
      FROM messages
      WHERE thread_id = :tid
      ORDER BY sent_at ASC
    """, tid=thread_id)

    return render_template('messages/thread.html',
                           thread_id=thread_id,
                           order_id=z["order_id"],
                           buyer_name=z["buyer_name"],
                           seller_name=z["seller_name"],
                           messages=msgs)

# JSON APIs

@bp.post("/api/messages/thread")
@login_required
def api_get_or_create_thread():
    data = request.get_json(silent=True) or {}
    order_id = int(data.get("order_id", 0))
    seller_id = int(data.get("seller_user_id", 0))  # sellers.id
    if order_id <= 0 or seller_id <= 0:
        return jsonify({"ok": False, "error": "bad input"}), 400

    ok = app.db.query_one("""
        SELECT 1
        FROM orders o
        JOIN order_sellers os ON os.order_id = o.order_id
        WHERE o.order_id = :oid AND o.buyer_id = :uid AND os.seller_id = :sid
        LIMIT 1
    """, oid=order_id, uid=current_user.id, sid=seller_id)
    if not ok:
        return jsonify({"ok": False, "error": "no such seller for this order"}), 400

    row = app.db.query_one("""
        SELECT thread_id
        FROM message_threads
        WHERE order_id = :oid AND seller_user_id = :sid AND buyer_user_id = :uid
    """, oid=order_id, sid=seller_id, uid=current_user.id)
    if row:
        return jsonify({"ok": True, "thread_id": row["thread_id"]})

    created = app.db.query_one("""
        INSERT INTO message_threads(order_id, seller_user_id, buyer_user_id)
        VALUES (:oid, :sid, :uid)
        ON CONFLICT (order_id, seller_user_id, buyer_user_id) DO NOTHING
        RETURNING thread_id
    """, oid=order_id, sid=seller_id, uid=current_user.id)
    if created:
        return jsonify({"ok": True, "thread_id": created["thread_id"]})

    row = app.db.query_one("""
        SELECT thread_id
        FROM message_threads
        WHERE order_id = :oid AND seller_user_id = :sid AND buyer_user_id = :uid
    """, oid=order_id, sid=seller_id, uid=current_user.id)
    return jsonify({"ok": True, "thread_id": row["thread_id"]})


def _can_post(thread_id: int, uid: int) -> bool:
    z = app.db.query_one("""
      SELECT mt.buyer_user_id, s.user_id AS seller_user_account
      FROM message_threads mt
      JOIN sellers s ON s.id = mt.seller_user_id
      WHERE mt.thread_id = :tid
    """, tid=thread_id)
    return bool(z and uid in (z["buyer_user_id"], z["seller_user_account"]))


@bp.get("/api/messages/<int:thread_id>")
@login_required
def api_fetch_messages(thread_id: int):
    if not _can_post(thread_id, current_user.id):
        return jsonify({"ok": False, "error": "no access"}), 403
    rows = app.db.query_all("""
        SELECT message_id, sender_user_id, body, sent_at
        FROM messages
        WHERE thread_id = :tid
        ORDER BY sent_at ASC
    """, tid=thread_id)
    return jsonify({"ok": True, "items": rows})


@bp.post("/api/messages/<int:thread_id>")
@login_required
def api_send_message(thread_id: int):
    if not _can_post(thread_id, current_user.id):
        return jsonify({"ok": False, "error": "no access"}), 403
    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"ok": False, "error": "empty"}), 400
    
    # Check for profanity
    if profanity.contains_profanity(body):
        return jsonify({"ok": False, "error": "Your message contains inappropriate language. Please revise your message."}), 400
    
    row = app.db.query_one("""
        INSERT INTO messages(thread_id, sender_user_id, body)
        VALUES (:tid, :uid, :body)
        RETURNING message_id, sent_at
    """, tid=thread_id, uid=current_user.id, body=body)
    return jsonify({"ok": True, "message_id": row["message_id"], "sent_at": row["sent_at"].isoformat()})


@bp.delete("/api/messages/<int:message_id>")
@login_required
def api_delete_message(message_id: int):
    from datetime import datetime
    
    row = app.db.query_one("""
        SELECT sender_user_id, sent_at, thread_id
        FROM messages
        WHERE message_id = :mid
    """, mid=message_id)
    
    if not row:
        return jsonify({"ok": False, "error": "Message not found"}), 404
    
    if row["sender_user_id"] != current_user.id:
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    
    # Check if message is within 1 minute using naive datetime since DB uses naive
    sent_at = row["sent_at"]
    now = datetime.now()
    time_diff = (now - sent_at).total_seconds()
    
    if time_diff > 60:
        return jsonify({"ok": False, "error": "Message can only be undone within 1 minute"}), 400
    
    thread_id = row["thread_id"]
    if not _can_post(thread_id, current_user.id):
        return jsonify({"ok": False, "error": "No access to this thread"}), 403
    
    # Delete the message
    app.db.execute("""
        DELETE FROM messages WHERE message_id = :mid
    """, mid=message_id)
    
    return jsonify({"ok": True})

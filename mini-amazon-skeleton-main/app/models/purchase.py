from flask import current_app as app


class Purchase:
    def __init__(self,
                 id: int,
                 product_id: int,
                 product_name: str,
                 price_cents: int,
                 quantity: int,
                 total_cents: int,
                 time_purchased,
                 seller_id: int,
                 seller_name: str,
                 balance_after_cents: int | None = None):
        self.id = id
        self.product_id = product_id
        self.product_name = product_name
        self.price_cents = price_cents
        self.quantity = quantity
        self.total_cents = total_cents
        self.time_purchased = time_purchased
        self.seller_id = seller_id
        self.seller_name = seller_name
        self.balance_after_cents = balance_after_cents

    @staticmethod
    def get(id: int):
        """
        Return ALL line items in a single order (order_id = id).
        """
        rows = app.db.execute("""
            SELECT
                oi.order_id        AS id,
                p.id               AS product_id,
                p.name             AS product_name,
                oi.unit_price_final_cents AS price_cents,
                oi.quantity        AS quantity,
                (oi.unit_price_final_cents * oi.quantity) AS total_cents,
                o.placed_at        AS time_purchased,
                oi.seller_id       AS seller_id,
                u.full_name        AS seller_name,
                NULL               AS balance_after_cents
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            JOIN products p ON p.id = oi.product_id
            JOIN sellers s ON s.id = oi.seller_id
            JOIN users u ON u.id = s.user_id
            WHERE o.order_id = :id
            ORDER BY o.placed_at DESC, oi.product_id
        """, id=id)

        return [Purchase(*row) for row in rows]

    @staticmethod
    def get_all_by_uid_since(uid: int, since):
        """
        Return all line items purchased by this user since `since` timestamp.
        """
        rows = app.db.execute("""
            SELECT
                oi.order_id        AS id,
                p.id               AS product_id,
                p.name             AS product_name,
                oi.unit_price_final_cents AS price_cents,
                oi.quantity        AS quantity,
                (oi.unit_price_final_cents * oi.quantity) AS total_cents,
                o.placed_at        AS time_purchased,
                oi.seller_id       AS seller_id,
                u.full_name        AS seller_name,
                NULL               AS balance_after_cents
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            JOIN products p ON p.id = oi.product_id
            JOIN sellers s ON s.id = oi.seller_id
            JOIN users u ON u.id = s.user_id
            WHERE o.buyer_id = :uid
              AND o.placed_at >= :since
            ORDER BY o.placed_at DESC, oi.order_id, oi.product_id
        """, uid=uid, since=since)

        return [Purchase(*row) for row in rows]

    @staticmethod
    def get_all_by_uid(uid: int,
                       limit: int = 50,
                       offset: int = 0,
                       q: str | None = None,
                       seller_id: int | None = None,
                       start_date: str | None = None,
                       end_date: str | None = None):
        """
        Return list of Purchase(...) for a given user,
        with optional filters:
          q          - substring match on product name (case-insensitive)
          seller_id  - only items from this seller
          start_date - placed_at >= this day
          end_date   - placed_at <= this day (inclusive)
        """

        where_clauses = ["o.buyer_id = :uid"]
        params = {
            "uid": uid,
            "limit": limit,
            "offset": offset
        }

        if q:
            where_clauses.append("LOWER(p.name) LIKE LOWER('%' || :q || '%')")
            params["q"] = q

        if seller_id:
            where_clauses.append("oi.seller_id = :seller_id")
            params["seller_id"] = seller_id

        if start_date:
            where_clauses.append("o.placed_at >= :start_date::timestamp")
            params["start_date"] = start_date

        if end_date:
            where_clauses.append("o.placed_at < (:end_date::date + INTERVAL '1 day')")
            params["end_date"] = end_date

        where_sql = " AND ".join(where_clauses)

        rows = app.db.execute(f"""
            WITH user_txns AS (
                SELECT
                    order_id,
                    SUM(amount) OVER (
                        PARTITION BY user_id
                        ORDER BY created_at ASC, id ASC
                    ) as running_bal
                FROM transactions
                WHERE user_id = :uid
            )
            SELECT
                oi.order_id        AS id,
                p.id               AS product_id,
                p.name             AS product_name,
                oi.unit_price_final_cents AS price_cents,
                oi.quantity        AS quantity,
                (oi.unit_price_final_cents * oi.quantity) AS total_cents,
                o.placed_at        AS time_purchased,
                oi.seller_id       AS seller_id,
                u.full_name        AS seller_name,
                CAST(ut.running_bal * 100 AS INT) AS balance_after_cents
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            JOIN products p ON p.id = oi.product_id
            JOIN sellers s ON s.id = oi.seller_id
            JOIN users u ON u.id = s.user_id
            LEFT JOIN user_txns ut ON ut.order_id = o.order_id
            WHERE {where_sql}
            ORDER BY o.placed_at DESC, oi.order_id, oi.product_id
            LIMIT :limit OFFSET :offset
        """, **params)

        return [Purchase(*row) for row in rows]

    @staticmethod
    def spending_summary(uid: int):
        """
        Small helper for analytics dashboard:
        total spent (all time), first purchase, last purchase, #orders
        """
        rows = app.db.execute("""
            SELECT
                SUM(oi.unit_price_final_cents * oi.quantity) AS total_cents,
                MIN(o.placed_at) AS first_purchase,
                MAX(o.placed_at) AS last_purchase,
                COUNT(DISTINCT o.order_id) AS num_orders
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.buyer_id = :uid
        """, uid=uid)

        if not rows:
            return {
                "total_spent_cents": 0,
                "first_purchase": None,
                "last_purchase": None,
                "num_orders": 0
            }

        row = rows[0]
        return {
            "total_spent_cents": row[0] if row[0] is not None else 0,
            "first_purchase": row[1],
            "last_purchase": row[2],
            "num_orders": row[3] if row[3] is not None else 0
        }
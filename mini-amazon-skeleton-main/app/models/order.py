from flask import current_app as app


class Order:
    def __init__(self, order_id: int, buyer_id: int, placed_at, shipping_address: str | None, order_fulfilled_at, status: str):
        self.order_id = order_id
        self.buyer_id = buyer_id
        self.placed_at = placed_at
        self.shipping_address = shipping_address
        self.order_fulfilled_at = order_fulfilled_at
        self.status = status

    @staticmethod
    def for_buyer(buyer_id: int):
        rows = app.db.execute('''
SELECT order_id, buyer_id, placed_at, shipping_address, order_fulfilled_at, status
FROM orders WHERE buyer_id = :buyer_id ORDER BY placed_at DESC
''', buyer_id=buyer_id)
        return [Order(*row) for row in rows]

    @staticmethod
    def get(order_id: int, buyer_id: int | None = None):
        if buyer_id is None:
            rows = app.db.execute('''
SELECT order_id, buyer_id, placed_at, shipping_address, order_fulfilled_at, status
FROM orders WHERE order_id = :order_id
''', order_id=order_id)
        else:
            rows = app.db.execute('''
SELECT order_id, buyer_id, placed_at, shipping_address, order_fulfilled_at, status
FROM orders WHERE order_id = :order_id AND buyer_id = :buyer_id
''', order_id=order_id, buyer_id=buyer_id)
        return Order(*rows[0]) if rows else None

    @staticmethod
    def get_history(uid: int, limit: int=10, offset: int=0, q: str=None, seller_id: int=None, start_date: str=None, end_date: str=None):
        # 1. Find matching Order IDs
        where_clauses = ["o.buyer_id = :uid"]
        params = {"uid": uid}
        
        # Joins needed for filtering
        joins = []
        # We use a set to track added joins to avoid duplicates if logic gets complex, 
        # but here simple flags work.
        joined_items = False
        
        if q:
            joins.append("JOIN order_items oi_filter ON o.order_id = oi_filter.order_id")
            joins.append("JOIN products p_filter ON oi_filter.product_id = p_filter.id")
            where_clauses.append("LOWER(p_filter.name) LIKE LOWER('%' || :q || '%')")
            params["q"] = q
            joined_items = True
        
        if seller_id:
            if not joined_items:
                joins.append("JOIN order_items oi_filter ON o.order_id = oi_filter.order_id")
                joined_items = True
            where_clauses.append("oi_filter.seller_id = :seller_id")
            params["seller_id"] = seller_id

        if start_date:
            where_clauses.append("o.placed_at >= :start_date::timestamp")
            params["start_date"] = start_date
        if end_date:
            where_clauses.append("o.placed_at < (:end_date::date + INTERVAL '1 day')")
            params["end_date"] = end_date

        where_sql = " AND ".join(where_clauses)
        join_sql = " ".join(joins)

        # Query for IDs
        query_ids = f"""
            SELECT DISTINCT o.order_id, o.placed_at
            FROM orders o
            {join_sql}
            WHERE {where_sql}
            ORDER BY o.placed_at DESC, o.order_id DESC
            LIMIT :limit OFFSET :offset
        """
        
        params["limit"] = limit
        params["offset"] = offset
        
        rows_ids = app.db.execute(query_ids, **params)
        if not rows_ids:
            return []
            
        order_ids = [r[0] for r in rows_ids]
        
        # 2. Fetch details for these orders
        ids_str = ", ".join(str(oid) for oid in order_ids)
        
        query_details = f"""
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
                o.order_id,
                o.placed_at,
                o.status,
                o.order_fulfilled_at,
                oi.product_id,
                p.name             AS product_name,
                oi.seller_id,
                u.full_name        AS seller_name,
                u.id               AS seller_user_id,
                oi.quantity,
                oi.unit_price_final_cents,
                (oi.unit_price_final_cents * oi.quantity) AS item_total_cents,
                CAST(ut.running_bal * 100 AS INT) AS balance_after_cents
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            JOIN products p ON p.id = oi.product_id
            JOIN sellers s ON s.id = oi.seller_id
            JOIN users u ON u.id = s.user_id
            LEFT JOIN user_txns ut ON ut.order_id = o.order_id
            WHERE o.order_id IN ({ids_str})
            ORDER BY o.placed_at DESC, o.order_id DESC, oi.product_id
        """
        
        rows_details = app.db.execute(query_details, uid=uid)
        
        # 3. Group by Order
        orders = []
        current_order = None
        
        # Since we ordered by order_id DESC, we can iterate and group
        for row in rows_details:
            oid = row[0]
            if current_order is None or current_order['id'] != oid:
                current_order = {
                    'id': oid,
                    'placed_at': row[1],
                    'status': row[2],
                    'fulfilled_at': row[3],
                    'balance_after_cents': row[12],
                    'line_items': [],
                    'total_cents': 0
                }
                orders.append(current_order)
            
            item = {
                'product_id': row[4],
                'product_name': row[5],
                'seller_id': row[6],
                'seller_name': row[7],
                'seller_user_id': row[8],
                'quantity': row[9],
                'price_cents': row[10],
                'total_cents': row[11]
            }
            current_order['line_items'].append(item)
            current_order['total_cents'] += item['total_cents']
            
        return orders



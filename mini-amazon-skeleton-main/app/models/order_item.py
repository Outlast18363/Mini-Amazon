from flask import current_app as app


class OrderItem:
    def __init__(self, order_id: int, product_id: int, seller_id: int, quantity: int, unit_price_final_cents: int, discount_cents: int, fulfilled_at):
        self.order_id = order_id
        self.product_id = product_id
        self.seller_id = seller_id
        self.quantity = quantity
        self.unit_price_final_cents = unit_price_final_cents
        self.discount_cents = discount_cents
        self.fulfilled_at = fulfilled_at

    @staticmethod
    def for_order(order_id: int):
        rows = app.db.execute('''
SELECT order_id, product_id, seller_id, quantity, unit_price_final_cents, discount_cents, fulfilled_at
FROM order_items WHERE order_id = :order_id
''', order_id=order_id)
        return [OrderItem(*row) for row in rows]



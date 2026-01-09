from flask import current_app as app


class InventoryItem:
    def __init__(self, seller_id: int, product_id: int, price_cents: int, quantity_on_hand: int, updated_at):
        self.seller_id = seller_id
        self.product_id = product_id
        self.price_cents = price_cents
        self.quantity_on_hand = quantity_on_hand
        self.updated_at = updated_at

    @staticmethod
    def for_seller(seller_id: int):
        rows = app.db.execute('''
SELECT seller_id, product_id, price_cents, quantity_on_hand, updated_at
FROM inventory WHERE seller_id = :seller_id
''', seller_id=seller_id)
        return [InventoryItem(*row) for row in rows]

    @staticmethod
    def offers_for_product(product_id: int):
        rows = app.db.execute('''
SELECT seller_id, product_id, price_cents, quantity_on_hand, updated_at
FROM inventory WHERE product_id = :product_id
''', product_id=product_id)
        return [InventoryItem(*row) for row in rows]

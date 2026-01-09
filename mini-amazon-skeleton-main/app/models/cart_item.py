from flask import current_app as app


class CartItem:
    def __init__(self, user_id: int, product_id: int, seller_id: int, quantity: int, is_in_cart: bool,
                 image_url: str = None, description: str = None, product_name: str = None,
                 seller_name: str = None, unit_price_cents: int = None, inventory_quantity: int = None):
        self.user_id = user_id
        self.product_id = product_id
        self.seller_id = seller_id
        self.quantity = quantity
        self.is_in_cart = is_in_cart

        # product/seller info
        self.image_url = image_url
        self.description = description
        self.product_name = product_name
        self.seller_name = seller_name
        self.unit_price_cents = unit_price_cents
        self.inventory_quantity = inventory_quantity

    @staticmethod
    def for_user(user_id: int, in_cart: bool = True):
        rows = app.db.execute('''
SELECT c.user_id, c.product_id, c.seller_id, c.quantity, c.is_in_cart,
       p.image_url, p.description, p.name,
       u.full_name AS seller_name,
       i.price_cents,
       i.quantity_on_hand
FROM cart_items c
JOIN products p ON c.product_id = p.id
JOIN sellers s ON s.id = c.seller_id
JOIN users u ON u.id = s.user_id
JOIN inventory i ON i.seller_id = c.seller_id AND i.product_id = c.product_id
WHERE c.user_id = :user_id AND c.is_in_cart = :in_cart
ORDER BY c.product_id
''', user_id=user_id, in_cart=in_cart) 
        # extend CartItem to store product info as attributes (image_url, description)
        items = []
        for row in rows:
            item = CartItem(
                row[0],  # user_id
                row[1],  # product_id
                row[2],  # seller_id
                row[3],  # quantity
                row[4],  # is_in_cart
                row[5],  # image_url
                row[6],  # description
                row[7],  # product_name
                row[8],  # seller_name
                row[9],  # unit_price_cents
                row[10]  # inventory_quantity
            )
            items.append(item)
        return items

    @staticmethod
    def add_to_cart(user_id, product_id, seller_id, quantity):
        # Check if the item is already in the cart
        rows = app.db.execute('''
SELECT quantity
FROM cart_items
WHERE user_id = :user_id AND product_id = :product_id AND seller_id = :seller_id AND is_in_cart = TRUE
''', user_id=user_id, product_id=product_id, seller_id=seller_id)

        current_quantity = rows[0][0] if rows else 0
        if current_quantity > 0:
            app.db.execute('''
UPDATE cart_items
SET quantity = :quantity
WHERE user_id = :user_id AND product_id = :product_id AND seller_id = :seller_id AND is_in_cart = TRUE
''', user_id=user_id, product_id=product_id, seller_id=seller_id, quantity=quantity)
        else:
            app.db.execute('''
INSERT INTO cart_items (user_id, product_id, seller_id, quantity, is_in_cart)
VALUES (:user_id, :product_id, :seller_id, :quantity, TRUE)
''', user_id=user_id, product_id=product_id, seller_id=seller_id, quantity=quantity)

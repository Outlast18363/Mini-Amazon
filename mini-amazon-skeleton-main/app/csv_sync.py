import csv
import os
from flask import current_app as app


def _generate_path(filename: str) -> str:
    base = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base, 'db', 'generate', filename)


def export_cart_items():
    path = _generate_path('CartItems.csv')
    rows = app.db.execute('''
SELECT user_id, product_id, seller_id, quantity, is_in_cart
FROM cart_items
ORDER BY user_id, product_id, seller_id, is_in_cart
''')
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(['' if v is None else v for v in row])


def export_users():
    path = _generate_path('Users.csv')
    rows = app.db.execute('''
SELECT id, email, full_name, address, password_hash, balance, created_at
FROM users
ORDER BY id
''')
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(['' if v is None else v for v in row])


def export_inventory():
    path = _generate_path('Inventory.csv')
    rows = app.db.execute('''
SELECT seller_id, product_id, price_cents, quantity_on_hand, updated_at
FROM inventory
ORDER BY seller_id, product_id
''')
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(['' if v is None else v for v in row])


def export_orders():
    path = _generate_path('Orders.csv')
    rows = app.db.execute('''
SELECT order_id, buyer_id, placed_at, shipping_address, order_fulfilled_at, status
FROM orders
ORDER BY order_id
''')
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(['' if v is None else v for v in row])


def export_order_items():
    path = _generate_path('OrderItems.csv')
    rows = app.db.execute('''
SELECT order_id, product_id, seller_id, quantity, unit_price_final_cents, discount_cents, fulfilled_at
FROM order_items
ORDER BY order_id, product_id, seller_id
''')
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(['' if v is None else v for v in row])



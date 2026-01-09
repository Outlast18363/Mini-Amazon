from werkzeug.security import generate_password_hash
import csv
import random
from typing import Dict, List, Tuple, Set
from faker import Faker
from pathlib import Path


# Tunable volumes
num_users = 100
num_categories = 10
num_products = 100
num_orders = 80

Faker.seed(0)
random.seed(0)
fake = Faker()

# Ensure outputs are written next to this script regardless of CWD
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR
OUT_DIR.mkdir(parents=True, exist_ok=True)


def get_csv_writer(f):
    return csv.writer(f, dialect='unix')


def gen_users(num_users: int) -> Dict[int, Dict[str, str]]:
    users: Dict[int, Dict[str, str]] = {}
    with open(OUT_DIR / 'Users.csv', 'w') as f:
        writer = get_csv_writer(f)
        print('Users...', end=' ', flush=True)
        for idx in range(1, num_users + 1):
            if idx % 20 == 0:
                print(f'{idx}', end=' ', flush=True)
            profile = fake.profile()
            email = profile['mail']
            full_name = profile['name']
            address = fake.address().replace('\n', ', ')
            plain_password = f'pass{idx}'
            password_hash = generate_password_hash(plain_password)
            balance_cents = random.randint(0, 100_000)
            balance = f'{balance_cents/100:.2f}'
            writer.writerow([idx, email, full_name, address, password_hash, balance])
            users[idx] = {
                'email': email,
                'full_name': full_name,
                'address': address,
            }
        print(f' {num_users} generated')
    return users


def gen_sellers(users: Dict[int, Dict[str, str]]) -> Tuple[Dict[int, int], List[int]]:
    user_ids: List[int] = list(users.keys())
    # Pick ~25% of users to be sellers, at least 10
    num_sellers = max(10, len(user_ids) // 4)
    seller_users = sorted(random.sample(user_ids, num_sellers))
    seller_id_to_user_id: Dict[int, int] = {}
    with open(OUT_DIR / 'Sellers.csv', 'w') as f:
        writer = get_csv_writer(f)
        print('Sellers...', end=' ', flush=True)
        for sid, user_id in enumerate(seller_users, start=1):
            if sid % 20 == 0:
                print(f'{sid}', end=' ', flush=True)
            writer.writerow([sid, user_id])
            seller_id_to_user_id[sid] = user_id
        print(f' {len(seller_users)} generated')
    seller_ids = list(seller_id_to_user_id.keys())
    return seller_id_to_user_id, seller_ids


def gen_categories(num_categories: int) -> List[Tuple[int, str, str]]:
    categories: List[Tuple[int, str, str]] = []
    with open(OUT_DIR / 'Categories.csv', 'w') as f:
        writer = get_csv_writer(f)
        print('Categories...', end=' ', flush=True)
        for cid in range(1, num_categories + 1):
            if cid % 10 == 0:
                print(f'{cid}', end=' ', flush=True)
            name = f"{fake.word().title()}"
            # Parent is any existing earlier category, or None
            if cid == 1 or random.random() < 0.4:
                parent_id_val = ''  # NULL
            else:
                parent_id_val = str(random.randint(1, cid - 1))
            writer.writerow([cid, name, parent_id_val])
            categories.append((cid, name, parent_id_val))
        print(f' {num_categories} generated')
    return categories


def gen_products(num_products: int, category_ids: List[int], seller_id_to_user_id: Dict[int, int]) -> List[int]:
    product_ids: List[int] = []
    seller_user_ids: List[int] = list(seller_id_to_user_id.values())
    with open(OUT_DIR / 'Products.csv', 'w') as f:
        writer = get_csv_writer(f)
        print('Products...', end=' ', flush=True)
        for pid in range(1, num_products + 1):
            if pid % 100 == 0:
                print(f'{pid}', end=' ', flush=True)
            name = fake.sentence(nb_words=4).rstrip('.')
            description = fake.paragraph(nb_sentences=3)
            image_url = f'https://picsum.photos/seed/{pid}/400/300'
            category_id = random.choice(category_ids)
            # Use a seller's user_id as the creator
            created_by = random.choice(seller_user_ids) if seller_user_ids else 1
            writer.writerow([pid, name, description, image_url, category_id, created_by])
            product_ids.append(pid)
        print(f' {num_products} generated')
    return product_ids


def gen_inventory(
    seller_ids: List[int],
    product_ids: List[int]
) -> Tuple[Dict[Tuple[int, int], int], Dict[int, List[int]]]:
    """Return (inventory_price_cents, product_to_sellers)"""
    inventory_price_cents: Dict[Tuple[int, int], int] = {}
    product_to_sellers: Dict[int, List[int]] = {}
    with open(OUT_DIR / 'Inventory.csv', 'w') as f:
        writer = get_csv_writer(f)
        print('Inventory...', end=' ', flush=True)
        for pid in product_ids:
            # Each product carried by 1-3 random sellers
            num_stockists = random.randint(1, min(3, max(1, len(seller_ids))))
            stockists = sorted(random.sample(seller_ids, num_stockists)) if seller_ids else []
            for sid in stockists:
                price_cents = random.randint(299, 49999)
                quantity_on_hand = random.randint(0, 100)
                writer.writerow([sid, pid, price_cents, quantity_on_hand])
                inventory_price_cents[(sid, pid)] = price_cents
                product_to_sellers.setdefault(pid, []).append(sid)
        print(' done')
    return inventory_price_cents, product_to_sellers


def gen_orders(num_orders: int, users: Dict[int, Dict[str, str]]) -> Dict[int, int]:
    oid_to_buyer: Dict[int, int] = {}
    user_ids: List[int] = list(users.keys())
    with open(OUT_DIR / 'Orders.csv', 'w') as f:
        writer = get_csv_writer(f)
        print('Orders...', end=' ', flush=True)
        for oid in range(1, num_orders + 1):
            if oid % 100 == 0:
                print(f'{oid}', end=' ', flush=True)
            buyer_id = random.choice(user_ids)
            shipping_address = users[buyer_id]['address']
            status = 'PENDING'
            writer.writerow([oid, buyer_id, shipping_address, status])
            oid_to_buyer[oid] = buyer_id
        print(f' {num_orders} generated')
    return oid_to_buyer


def gen_order_items(
    oid_to_buyer: Dict[int, int],
    product_ids: List[int],
    product_to_sellers: Dict[int, List[int]],
    inventory_price_cents: Dict[Tuple[int, int], int],
    seller_id_to_user_id: Dict[int, int]
) -> None:
    with open(OUT_DIR / 'OrderItems.csv', 'w') as f_items, \
         open(OUT_DIR / 'Transactions.csv', 'w') as f_txns:
        writer_items = get_csv_writer(f_items)
        writer_txns = get_csv_writer(f_txns)
        print('OrderItems & Transactions...', end=' ', flush=True)
        
        txn_id = 1
        for oid, buyer_id in oid_to_buyer.items():
            if oid % 100 == 0:
                print(f'{oid}', end=' ', flush=True)
            num_lines = random.randint(1, 4)
            used_pairs: Set[Tuple[int, int]] = set()
            
            order_total_cents = 0
            seller_income: Dict[int, int] = {} # seller_user_id -> cents

            for _ in range(num_lines):
                # Pick a product that has at least one seller
                pid = None
                tries = 0
                while tries < 10:
                    candidate_pid = random.choice(product_ids)
                    if product_to_sellers.get(candidate_pid):
                        pid = candidate_pid
                        break
                    tries += 1
                if pid is None:
                    continue  # skip if no stocked products exist
                sid = random.choice(product_to_sellers[pid])
                if (pid, sid) in used_pairs:
                    continue
                used_pairs.add((pid, sid))
                quantity = random.randint(1, 3)
                unit_price_cents = inventory_price_cents[(sid, pid)]
                discount_cents = 0
                fulfilled_at = ''  # NULL
                writer_items.writerow([
                    oid,
                    pid,
                    sid,
                    quantity,
                    unit_price_cents,
                    discount_cents,
                    fulfilled_at,
                ])
                
                line_total = unit_price_cents * quantity
                order_total_cents += line_total
                
                s_uid = seller_id_to_user_id[sid]
                seller_income[s_uid] = seller_income.get(s_uid, 0) + line_total

            # Generate transactions
            # 1. Buyer pays
            if order_total_cents > 0:
                writer_txns.writerow([txn_id, buyer_id, f'-{order_total_cents/100:.2f}', oid])
                txn_id += 1
            
            # 2. Sellers receive
            for s_uid, income in seller_income.items():
                writer_txns.writerow([txn_id, s_uid, f'{income/100:.2f}', oid])
                txn_id += 1

        print(' done')


if __name__ == '__main__':
    users = gen_users(num_users)
    seller_id_to_user_id, seller_ids = gen_sellers(users)
    categories = gen_categories(num_categories)
    category_ids = [cid for (cid, _name, _parent) in categories]
    products = gen_products(num_products, category_ids, seller_id_to_user_id)
    inventory_price_cents, product_to_sellers = gen_inventory(seller_ids, products)
    oid_to_buyer = gen_orders(num_orders, users)
    gen_order_items(oid_to_buyer, products, product_to_sellers, inventory_price_cents, seller_id_to_user_id)

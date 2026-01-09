from werkzeug.security import generate_password_hash
import csv
import random
from typing import Dict, List, Tuple, Set, Any
from faker import Faker
from pathlib import Path
from datetime import datetime

# --- Configuration ---
num_users = 150
num_products = 800
num_orders = 1500
num_categories = 12

Faker.seed(0)
random.seed(0)
fake = Faker()

# Ensure outputs are written next to this script regardless of CWD
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR
OUT_DIR.mkdir(parents=True, exist_ok=True)

def get_csv_writer(f):
    return csv.writer(f, dialect='unix')

# ---------------------------------------------------------
# Core Generators
# ---------------------------------------------------------

def init_users(num_users: int) -> Dict[int, Dict[str, Any]]:
    """
    Generates user data in memory.
    Returns: Dict[user_id, user_info_dict]
    """
    print(f"Generating {num_users} users (in-memory)...")
    users = {}
    for uid in range(1, num_users + 1):
        profile = fake.profile()
        email = profile['mail']
        # Ensure unique emails
        email = f"{uid}_{email}" 
        full_name = profile['name']
        address = fake.address().replace('\n', ', ')
        password = f"pass{uid}"
        password_hash = generate_password_hash(password)
        balance = 0.0

        users[uid] = {
            'email': email,
            'full_name': full_name,
            'address': address,
            'password_hash': password_hash,
            'balance': balance,
            'created_at': fake.date_time_this_year()
        }
    return users

def save_users(users: Dict[int, Dict[str, Any]]) -> None:
    """
    Writes Users.csv from the users dictionary.
    """
    print("Saving users to CSV...")
    with open(OUT_DIR / 'Users.csv', 'w') as f:
        writer = get_csv_writer(f)
        for uid, info in users.items():
            writer.writerow([
                uid,
                info['email'],
                info['full_name'],
                info['address'],
                info['password_hash'],
                f"{info['balance']:.2f}",
                info['created_at']
            ])

def gen_sellers(users: Dict[int, Dict]) -> Tuple[Dict[int, int], List[int]]:
    """
    Generates Sellers.csv (Subset of users)
    Returns: (seller_id_to_user_id_map, list_of_seller_ids)
    """
    print("Generating sellers...")
    seller_id_to_user_id = {}
    seller_ids = []
    
    # 20% of users are sellers
    potential_users = list(users.keys())
    num_sellers = max(1, int(len(users) * 0.2))
    chosen_users = random.sample(potential_users, num_sellers)

    with open(OUT_DIR / 'Sellers.csv', 'w') as f:
        writer = get_csv_writer(f)
        for i, user_id in enumerate(chosen_users, 1):
            writer.writerow([i, user_id])
            seller_id_to_user_id[i] = user_id
            seller_ids.append(i)
            
    return seller_id_to_user_id, seller_ids

def gen_categories(num_categories: int) -> List[Tuple[int, str, Any]]:
    """
    Generates Categories.csv
    Returns: List of (cat_id, name, parent_id)
    """
    print(f"Generating {num_categories} categories...")
    categories = []
    with open(OUT_DIR / 'Categories.csv', 'w') as f:
        writer = get_csv_writer(f)
        for i in range(1, num_categories + 1):
            name = fake.unique.word().capitalize() + " " + fake.word().capitalize()
            # Simple hierarchy: every 3rd category is a child of the previous
            parent_id = (i - 1) if (i > 1 and i % 3 == 0) else None
            
            writer.writerow([i, name, parent_id])
            categories.append((i, name, parent_id))
    return categories


def gen_products(num_products: int, category_ids: List[int], users: Dict[int, Dict]) -> Tuple[List[int], Dict[int, int]]:
    """
    Generates Products.csv
    Returns: (List of product_ids, Dict {pid: cat_id})
    """
    print(f"Generating {num_products} products...")
    product_ids = []
    pid_to_cid = {}
    user_ids = list(users.keys())
    
    with open(OUT_DIR / 'Products.csv', 'w') as f:
        writer = get_csv_writer(f)
        for pid in range(1, num_products + 1):
            name = fake.sentence(nb_words=4).rstrip('.')
            desc = fake.sentence(nb_words=10)
            img_url = f'https://picsum.photos/seed/{pid}/400/300'
            cat_id = random.choice(category_ids)
            created_by = random.choice(user_ids)
            
            writer.writerow([pid, name, desc, img_url, cat_id, created_by, fake.date_time_this_year()])
            product_ids.append(pid)
            pid_to_cid[pid] = cat_id
            
    return product_ids, pid_to_cid

def gen_inventory(seller_ids: List[int], product_ids: List[int]) -> Tuple[Dict[Tuple[int, int], int], Dict[int, List[int]]]:
    """
    Generates Inventory.csv
    Returns: 
        1. inventory_price_map {(seller_id, product_id): price_cents}
        2. product_to_sellers_map {product_id: [seller_id, ...]}
    """
    print("Generating inventory...")
    inventory_price = {}
    product_to_sellers = {pid: [] for pid in product_ids}
    
    with open(OUT_DIR / 'Inventory.csv', 'w') as f:
        writer = get_csv_writer(f)
        
        # Each seller sells ~20 random products
        for sid in seller_ids:
            stock_products = random.sample(product_ids, k=random.randint(5, 30))
            for pid in stock_products:
                price = random.randint(500, 10000) # $5.00 to $100.00
                qty = random.randint(0, 100)
                
                writer.writerow([sid, pid, price, qty, fake.date_time_this_year()])
                
                inventory_price[(sid, pid)] = price
                product_to_sellers[pid].append(sid)
                
    return inventory_price, product_to_sellers

def gen_cart_items(num_lines: int, users: Dict[int, Dict], product_to_sellers: Dict[int, List[int]]) -> None:
    """Generates CartItems.csv"""
    print("Generating cart items...")
    user_ids = list(users.keys())
    product_ids = list(product_to_sellers.keys())
    generated = set()
    
    with open(OUT_DIR / 'CartItems.csv', 'w') as f:
        writer = get_csv_writer(f)
        count = 0
        while count < num_lines:
            uid = random.choice(user_ids)
            pid = random.choice(product_ids)
            sellers = product_to_sellers.get(pid)
            if not sellers: continue
            sid = random.choice(sellers)
            
            if (uid, pid, sid) in generated: continue
            generated.add((uid, pid, sid))
            
            is_in_cart = random.choice([True, False])
            qty = random.randint(1, 5)
            
            writer.writerow([uid, pid, sid, qty, is_in_cart])
            count += 1

# ---------------------------------------------------------
# Order Fulfillment Flow
# ---------------------------------------------------------

def gen_orders(num_orders: int, users: Dict[int, Dict]) -> Dict[int, int]:
    """
    Generates Orders.csv
    Returns: Dict {order_id: buyer_id}
    """
    print(f"Generating {num_orders} orders...")
    orders_map = {} # order_id -> buyer_id
    user_ids = list(users.keys())
    
    with open(OUT_DIR / 'Orders.csv', 'w') as f:
        writer = get_csv_writer(f)
        for oid in range(1, num_orders + 1):
            buyer_id = random.choice(user_ids)
            orders_map[oid] = buyer_id
            
            created = fake.date_time_this_year()
            status = random.choice(['PENDING', 'PARTIAL', 'FULFILLED'])
            fulfilled_at = created if status == 'FULFILLED' else None
            
            writer.writerow([oid, buyer_id, created, users[buyer_id]['address'], fulfilled_at, status])
            
    return orders_map

def gen_order_items(
    orders_map: Dict[int, int], 
    product_ids: List[int],
    product_to_sellers: Dict[int, List[int]],
    inventory_price: Dict[Tuple[int, int], int]
) -> Dict[int, Dict]:
    """
    Generates OrderItems.csv
    Returns: complex map for messaging { order_id: {'buyer_id': int, 'seller_ids': set(int)} }
    """
    print("Generating order items...")
    order_participants = {} 

    with open(OUT_DIR / 'OrderItems.csv', 'w') as f:
        writer = get_csv_writer(f)
        
        for oid, buyer_id in orders_map.items():
            order_participants[oid] = {'buyer_id': buyer_id, 'seller_ids': set()}
            
            num_items = random.randint(1, 5)
            items_in_this_order = set()
            
            for _ in range(num_items):
                pid = random.choice(product_ids)
                sellers = product_to_sellers.get(pid)
                if not sellers: continue
                sid = random.choice(sellers)
                
                if (pid, sid) in items_in_this_order: continue
                items_in_this_order.add((pid, sid))
                
                price = inventory_price.get((sid, pid), 1000)
                qty = random.randint(1, 3)
                fulfilled_at = fake.date_time_this_year() if random.random() > 0.3 else None
                
                writer.writerow([oid, pid, sid, qty, price, 0, fulfilled_at])
                
                order_participants[oid]['seller_ids'].add(sid)

    return order_participants

def gen_transactions(users: Dict[int, Dict], orders_map: Dict[int, int]) -> None:
    """Generates Transactions.csv and updates user balances"""
    print("Generating transactions...")
    user_ids = list(users.keys())
    txn_id = 1
    
    with open(OUT_DIR / 'Transactions.csv', 'w') as f:
        writer = get_csv_writer(f)
        
        # 1. Initial deposits
        for uid in user_ids:
            amt = random.uniform(100, 5000)
            users[uid]['balance'] += amt
            writer.writerow([txn_id, uid, f"{amt:.2f}", None, fake.date_time_this_year()])
            txn_id += 1
            
        # 2. Order payments
        for oid, buyer_id in orders_map.items():
            amt = random.uniform(-200, -10)
            users[buyer_id]['balance'] += amt
            writer.writerow([txn_id, buyer_id, f"{amt:.2f}", oid, fake.date_time_this_year()])
            txn_id += 1

# ---------------------------------------------------------
# Feedback & Messages
# ---------------------------------------------------------

def gen_reviews(users: Dict[int, Dict], products: List[int], seller_ids: List[int]) -> int:
    """
    Generates ProductReviews.csv and SellerReviews.csv
    Returns: The count of product reviews generated (for the helpful votes generator)
    """
    print("Generating reviews...")
    user_ids = list(users.keys())
    
    product_review_count = 0
    
    # Product Reviews
    with open(OUT_DIR / 'ProductReviews.csv', 'w') as f:
        writer = get_csv_writer(f)
        existing = set()
        for _ in range(300):
            uid = random.choice(user_ids)
            pid = random.choice(products)
            if (uid, pid) in existing: continue
            existing.add((uid, pid))
            
            product_review_count += 1
            # ID is implied serial/count
            writer.writerow([
                product_review_count, 
                pid, uid, random.randint(1, 5), fake.sentence(), fake.paragraph(), 
                fake.date_time_this_year(), fake.date_time_this_year()
            ])

    # Seller Reviews
    with open(OUT_DIR / 'SellerReviews.csv', 'w') as f:
        writer = get_csv_writer(f)
        existing_sell = set()
        count = 0
        for _ in range(100):
            uid = random.choice(user_ids)
            sid = random.choice(seller_ids)
            if (uid, sid) in existing_sell: continue
            existing_sell.add((uid, sid))
            
            count += 1
            writer.writerow([
                count,
                sid, uid, random.randint(1, 5), fake.sentence(), fake.paragraph(),
                fake.date_time_this_year(), fake.date_time_this_year()
            ])
            
    return product_review_count

def gen_helpful_votes(num_product_reviews: int, users: Dict[int, Dict]) -> None:
    """Generates ReviewHelpfulVotes.csv"""
    print("Generating review helpful votes...")
    user_ids = list(users.keys())
    generated_votes = set()
    
    with open(OUT_DIR / 'ReviewHelpfulVotes.csv', 'w') as f:
        writer = get_csv_writer(f)
        # Generate ~200 votes
        for _ in range(200):
            # Pick a random review ID (1 to num_product_reviews)
            rid = random.randint(1, num_product_reviews)
            uid = random.choice(user_ids)
            
            if (rid, uid) in generated_votes: continue
            generated_votes.add((rid, uid))
            
            writer.writerow([rid, uid, fake.date_time_this_year()])

def gen_messages(order_participants: Dict[int, Dict]) -> None:
    """
    Generates MessageThreads.csv and Messages.csv
    """
    print("Generating messages...")
    thread_rows = []
    msg_rows = []
    
    thread_id = 1
    msg_id = 1
    
    for oid, info in order_participants.items():
        buyer = info['buyer_id']
        sellers = list(info['seller_ids'])
        
        if sellers and random.random() < 0.3:
            sid = random.choice(sellers)
            created_at = fake.date_time_this_year()
            
            thread_rows.append([thread_id, oid, sid, buyer, created_at])
            
            for _ in range(random.randint(2, 6)):
                sender = random.choice([buyer, sid])
                msg_rows.append([msg_id, thread_id, sender, fake.sentence(), created_at])
                msg_id += 1
                
            thread_id += 1

    with open(OUT_DIR / 'MessageThreads.csv', 'w') as f:
        get_csv_writer(f).writerows(thread_rows)

    with open(OUT_DIR / 'Messages.csv', 'w') as f:
        get_csv_writer(f).writerows(msg_rows)

# ---------------------------------------------------------
# Coupons
# ---------------------------------------------------------

def gen_coupons(num_coupons: int, product_ids: List[int], category_ids: List[int]) -> None:
    """
    Generates Coupons.csv
    """
    print(f"Generating {num_coupons} coupons...")
    
    with open(OUT_DIR / 'Coupons.csv', 'w') as f:
        writer = get_csv_writer(f)
        
        for i in range(1, num_coupons + 1):
            code = fake.unique.bothify(text='??##-??##-??##').upper()
            discount = random.randint(5, 50) # 5% to 50%
            
            # Expiration > 2030 (e.g., 2031-2035)
            start_date = datetime(2031, 1, 1)
            end_date = datetime(2035, 12, 31)
            expiration_time = fake.date_time_between_dates(datetime_start=start_date, datetime_end=end_date)
            
            # Determine type
            rand = random.random()
            if rand < 0.33:
                # Global
                pid = None
                cid = None
            elif rand < 0.66:
                # Product-specific
                pid = random.choice(product_ids)
                cid = None
            else:
                # Category-specific
                pid = None
                cid = random.choice(category_ids)
                
            writer.writerow([i, code, discount, expiration_time, pid, cid])


# ---------------------------------------------------------
# SPECIFIC TEST USER GENERATION
# ---------------------------------------------------------

def gen_specific_test_user(
    email: str, 
    password_plain: str, 
    existing_user_count: int,
    existing_order_count: int,
    product_to_sellers: Dict[int, List[int]],
    product_ids: List[int], # Added to support random reviews
    seller_ids: List[int],   # Added to support random reviews
    pid_to_cid: Dict[int, int] # Added for targeted coupons
) -> None:
    """
    Appends a specific test user with massive history to existing files.
    """
    print(f"\n--- Generating TEST USER: {email} ---")
    
    user_id = existing_user_count + 1
    pwd_hash = generate_password_hash(password_plain)
    
    # 2. Append Cart Items (15 items)
    product_ids_local = list(product_to_sellers.keys())
    with open(OUT_DIR / 'CartItems.csv', 'a') as f:
        writer = get_csv_writer(f)
        added = set()
        while len(added) < 15:
            pid = random.choice(product_ids_local)
            sellers = product_to_sellers.get(pid)
            if not sellers: continue
            sid = random.choice(sellers)
            if pid in added: continue
            added.add(pid)
            
            writer.writerow([user_id, pid, sid, random.randint(1, 5), True])

    # Capture items for coupon generation
    cart_pids = list(added)

    # 3. Append Orders, Items, Transactions, Messages
    new_orders = []
    new_items = []
    new_txns = []
    new_threads = []
    new_msgs = []
    
    # Start IDs safely above existing counts to avoid collision
    oid_start = existing_order_count + 2000 
    txn_start = 200000
    thread_start = 200000
    msg_start = 200020
    
    total_spent_cents = 0

    # Generate 20 past orders
    for i in range(20):
        current_oid = oid_start + i
        date = fake.date_time_this_year()
        
        # --- LOGIC CHANGE START: Generate Items First to Determine Status ---
        
        current_order_items = []
        sellers_involved = set()
        order_total = 0
        num_lines = random.randint(1, 6)
        fulfilled_items_count = 0
        
        for _ in range(num_lines):
            pid = random.choice(product_ids_local)
            sellers = product_to_sellers.get(pid)
            if not sellers: continue
            sid = random.choice(sellers)
            
            sellers_involved.add(sid)
            price = random.randint(1000, 5000)
            qty = random.randint(1, 3)
            line_total = price * qty
            order_total += line_total
            
            # Randomly determine if this specific item is fulfilled
            # 70% chance of being fulfilled to simulate active history
            is_item_fulfilled = random.random() < 0.7 
            item_fulfilled_at = date if is_item_fulfilled else None
            
            if is_item_fulfilled:
                fulfilled_items_count += 1
                
            current_order_items.append([
                current_oid, pid, sid, qty, price, 0, item_fulfilled_at
            ])
            
        total_spent_cents += order_total

        # Calculate Order Status based on items
        if fulfilled_items_count == 0:
            order_status = 'PENDING'
            order_fulfilled_at = None
        elif fulfilled_items_count == len(current_order_items):
            order_status = 'FULFILLED'
            order_fulfilled_at = date # Whole order finished
        else:
            order_status = 'PARTIAL'
            order_fulfilled_at = None # Not completely finished yet
            
        # --- LOGIC CHANGE END ---
        
        # Add Order
        new_orders.append([
            current_oid, user_id, date, "123 Test Lane, Tech City", order_fulfilled_at, order_status
        ])
        
        # Add Items
        new_items.extend(current_order_items)
            
        # Transaction
        new_txns.append([
            txn_start + i, user_id, f"-{order_total/100:.2f}", current_oid, date
        ])
        
        # Force messages on the first 6 orders, random otherwise
        if sellers_involved and (i < 6 or random.random() > 0.5):
            sid = list(sellers_involved)[0]
            new_threads.append([
                thread_start, current_oid, sid, user_id, date
            ])
            
            # Only generate dynamic messages for threads beyond the first 6
            # The first 6 threads (200000-200005) will have hardcoded messages appended later
            if thread_start > 200005:
                new_msgs.append([
                    msg_start, thread_start, user_id, "Is this item authentic?", date
                ])
                new_msgs.append([
                    msg_start+1, thread_start, sid, "Yes it is!", date
                ])
                msg_start += 2
                
            thread_start += 1

    # Add Initial Deposit for Test User
    # Start with 50,000.00
    initial_deposit = 50000.00
    deposit_date = "2025-01-01 00:00:00"
    new_txns.insert(0, [txn_start - 1, user_id, f"{initial_deposit:.2f}", None, deposit_date])

    # Calculate final balance
    final_balance = initial_deposit - (total_spent_cents / 100.0)


    # Append Hardcoded Messages (IDs 200000 - 200011)
    hardcoded_msgs = [
        [200000, 200000, 151, "Is this item authentic?", "2025-02-10 19:44:54.174099"],
        [200001, 200000, 17, "Yes it is!", "2025-02-10 19:44:54.174099"],
        [200002, 200001, 151, "Is this item authentic?", "2025-06-08 02:12:37.695449"],
        [200003, 200001, 1, "Yes it is!", "2025-06-08 02:12:37.695449"],
        [200004, 200002, 151, "Is this item authentic?", "2025-10-22 00:34:12.010683"],
        [200005, 200002, 29, "Yes it is!", "2025-10-22 00:34:12.010683"],
        [200006, 200003, 151, "Is this item authentic?", "2025-06-08 17:39:16.976500"],
        [200007, 200003, 13, "Yes it is!", "2025-06-08 17:39:16.976500"],
        [200008, 200004, 151, "Is this item authentic?", "2025-02-16 16:20:39.866429"],
        [200009, 200004, 21, "Yes it is!", "2025-02-16 16:20:39.866429"],
        [200010, 200005, 151, "Is this item authentic?", "2025-10-02 03:09:56.240293"],
        [200011, 200005, 1, "Yes it is!", "2025-10-02 03:09:56.240293"]
    ]
    new_msgs.extend(hardcoded_msgs)

    # 1. Append User (Moved to here to use final_balance)
    with open(OUT_DIR / 'Users.csv', 'a') as f:
        writer = get_csv_writer(f)
        writer.writerow([
            user_id, email, "Test Super User", "123 Test Lane, Tech City", 
            pwd_hash, f"{final_balance:.2f}", fake.date_time_this_year()
        ])

    # Write Orders/Items/Txns/Messages
    with open(OUT_DIR / 'Orders.csv', 'a') as f: get_csv_writer(f).writerows(new_orders)
    with open(OUT_DIR / 'OrderItems.csv', 'a') as f: get_csv_writer(f).writerows(new_items)
    with open(OUT_DIR / 'Transactions.csv', 'a') as f: get_csv_writer(f).writerows(new_txns)
    with open(OUT_DIR / 'MessageThreads.csv', 'a') as f: get_csv_writer(f).writerows(new_threads)
    with open(OUT_DIR / 'Messages.csv', 'a') as f: get_csv_writer(f).writerows(new_msgs)
    
    # 4. Append Reviews (NEW SECTION)
    # Using large ID offsets for reviews to avoid collision with general data
    prod_rev_start = 50000 
    sell_rev_start = 50000
    
    with open(OUT_DIR / 'ProductReviews.csv', 'a') as f:
        writer = get_csv_writer(f)
        # Generate 5 random product reviews from the user
        for i in range(5):
            pid = random.choice(product_ids)
            writer.writerow([
                prod_rev_start + i, pid, user_id, 5, 
                "Great Test Product!", "I loved testing this.", 
                fake.date_time_this_year(), fake.date_time_this_year()
            ])

    with open(OUT_DIR / 'SellerReviews.csv', 'a') as f:
        writer = get_csv_writer(f)
        # Generate 3 random seller reviews from the user
        # Use sample to ensure unique sellers and avoid duplicate key errors
        chosen_sellers = random.sample(seller_ids, min(3, len(seller_ids)))
        for i, sid in enumerate(chosen_sellers):
            writer.writerow([
                sell_rev_start + i, sid, user_id, 4, 
                "Good Seller", "Fast shipping, good test.", 
                fake.date_time_this_year(), fake.date_time_this_year()
            ])
            
    # 5. Append TEST USER Coupons
    # Ensure IDs don't conflict. gen_coupons used 1-100.
    coupon_id_start = 1000
    test_coupons = []
    
    # Common expiration for test coupons
    expiry = "2035-01-01 00:00:00"
    
    # 5.1 Global Coupon
    code_global = "TEST-Global-20"
    test_coupons.append([coupon_id_start, code_global, 20, expiry, None, None])
    
    # 5.2 Product Specific (pick first item in cart)
    if cart_pids:
        target_pid = cart_pids[0]
        code_item = f"TEST-Item-{target_pid}"
        test_coupons.append([coupon_id_start+1, code_item, 15, expiry, target_pid, None])
    else:
        code_item = "No-Item-In-Cart"
        
    # 5.3 Category Specific (pick category of first item in cart)
    if cart_pids:
        target_pid = cart_pids[0]
        target_cid = pid_to_cid.get(target_pid)
        if target_cid:
            code_cat = f"TEST-Cat-{target_cid}"
            test_coupons.append([coupon_id_start+2, code_cat, 10, expiry, None, target_cid])
        else:
            code_cat = "No-Cat-Found"
    else:
        code_cat = "No-Item-In-Cart"
        
    with open(OUT_DIR / 'Coupons.csv', 'a') as f:
        get_csv_writer(f).writerows(test_coupons)
    
    print(f"Test User '{email}' created.")
    print(f"Generated Test Coupons:")
    print(f"  Global:   {code_global} (20% off)")
    print(f"  Item:     {code_item} (15% off product {target_pid if cart_pids else 'N/A'})")
    print(f"  Category: {code_cat} (10% off category {target_cid if cart_pids and target_cid else 'N/A'})")

# ---------------------------------------------------------
# Main Execution
# ---------------------------------------------------------

if __name__ == '__main__':
    # 1. Core Entities
    users_map = init_users(num_users)
    seller_map, seller_ids = gen_sellers(users_map)
    cats = gen_categories(num_categories)
    cat_ids = [c[0] for c in cats]
    
    # 2. Products & Inventory
    product_ids, pid_to_cid = gen_products(num_products, cat_ids, users_map)
    inv_prices, prod_to_sellers = gen_inventory(seller_ids, product_ids)
    
    # 3. Orders Flow
    orders_map = gen_orders(num_orders, users_map) # Returns {oid: buyer_id}
    order_participants = gen_order_items(orders_map, product_ids, prod_to_sellers, inv_prices)
    
    # 4. Secondary Tables
    gen_cart_items(200, users_map, prod_to_sellers)
    gen_transactions(users_map, orders_map)
    
    # 5. Reviews & Votes
    prod_review_count = gen_reviews(users_map, product_ids, seller_ids)
    gen_helpful_votes(prod_review_count, users_map)
    
    # 6. Messages
    gen_messages(order_participants)

    # 7. Coupons
    gen_coupons(100, product_ids, cat_ids)

    # 8. Save Users (with updated balances)
    save_users(users_map)
    
    # 9. Explicit Test User (Updated with full data generation)
    gen_specific_test_user(
        email="awefewaf@gmail.com",
        password_plain="12345",
        existing_user_count=num_users,
        existing_order_count=num_orders,
        product_to_sellers=prod_to_sellers,
        product_ids=product_ids,
        seller_ids=seller_ids,
        pid_to_cid=pid_to_cid
    )
    
    print("Data generation complete. CSV files located in:", OUT_DIR)
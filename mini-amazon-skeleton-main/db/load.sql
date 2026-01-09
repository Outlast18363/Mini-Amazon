-- Users
\COPY users(id, email, full_name, address, password_hash, balance, created_at) FROM 'Users.csv' WITH DELIMITER ',' NULL '' CSV;
SELECT setval(pg_get_serial_sequence('users','id'), COALESCE((SELECT MAX(id)+1 FROM users), 1), false);

-- Sellers
\COPY sellers(id, user_id) FROM 'Sellers.csv' WITH DELIMITER ',' NULL '' CSV;
SELECT setval(pg_get_serial_sequence('sellers','id'), COALESCE((SELECT MAX(id)+1 FROM sellers), 1), false);

-- Categories
\COPY categories(id, name, parent_id) FROM 'Categories.csv' WITH DELIMITER ',' NULL '' CSV FORCE NULL parent_id;
SELECT setval(pg_get_serial_sequence('categories','id'), COALESCE((SELECT MAX(id)+1 FROM categories), 1), false);

-- Products
\COPY products(id, name, description, image_url, category_id, created_by, created_at) FROM 'Products.csv' WITH DELIMITER ',' NULL '' CSV;
SELECT setval(pg_get_serial_sequence('products','id'), COALESCE((SELECT MAX(id)+1 FROM products), 1), false);

-- Inventory
\COPY inventory(seller_id, product_id, price_cents, quantity_on_hand, updated_at) FROM 'Inventory.csv' WITH DELIMITER ',' NULL '' CSV;

-- Orders
-- FIX APPLIED HERE: Added FORCE NULL order_fulfilled_at
\COPY orders(order_id, buyer_id, placed_at, shipping_address, order_fulfilled_at, status) FROM 'Orders.csv' WITH DELIMITER ',' NULL '' CSV FORCE NULL order_fulfilled_at;
SELECT setval(pg_get_serial_sequence('orders','order_id'), COALESCE((SELECT MAX(order_id)+1 FROM orders), 1), false);

-- Order items
-- FIX APPLIED HERE: Added FORCE NULL fulfilled_at
\COPY order_items(order_id, product_id, seller_id, quantity, unit_price_final_cents, discount_cents, fulfilled_at) FROM 'OrderItems.csv' WITH DELIMITER ',' NULL '' CSV FORCE NULL fulfilled_at;

-- Transactions (You were missing this in your snippet, but your python generates it)
\COPY transactions(id, user_id, amount, order_id, created_at) FROM 'Transactions.csv' WITH DELIMITER ',' NULL '' CSV FORCE NULL order_id;
SELECT setval(pg_get_serial_sequence('transactions','id'), COALESCE((SELECT MAX(id)+1 FROM transactions), 1), false);

-- Cart items
\COPY cart_items(user_id, product_id, seller_id, quantity, is_in_cart) FROM 'CartItems.csv' WITH DELIMITER ',' NULL '' CSV;

-- Product Reviews (Your python generates this)
\COPY product_reviews(review_id, product_id, author_user_id, rating, title, body, created_at, updated_at) FROM 'ProductReviews.csv' WITH DELIMITER ',' NULL '' CSV;
SELECT setval(pg_get_serial_sequence('product_reviews','review_id'), COALESCE((SELECT MAX(review_id)+1 FROM product_reviews), 1), false);

-- Seller Reviews (Your python generates this)
\COPY seller_reviews(review_id, seller_user_id, author_user_id, rating, title, body, created_at, updated_at) FROM 'SellerReviews.csv' WITH DELIMITER ',' NULL '' CSV;
SELECT setval(pg_get_serial_sequence('seller_reviews','review_id'), COALESCE((SELECT MAX(review_id)+1 FROM seller_reviews), 1), false);

-- Review Helpful Votes (Your python generates this)
\COPY review_helpful_votes(review_id, voter_user_id, created_at) FROM 'ReviewHelpfulVotes.csv' WITH DELIMITER ',' NULL '' CSV;

-- Message Threads (Your python generates this)
\COPY message_threads(thread_id, order_id, seller_user_id, buyer_user_id, created_at) FROM 'MessageThreads.csv' WITH DELIMITER ',' NULL '' CSV;
SELECT setval(pg_get_serial_sequence('message_threads','thread_id'), COALESCE((SELECT MAX(thread_id)+1 FROM message_threads), 1), false);

-- Messages (Your python generates this)
\COPY messages(message_id, thread_id, sender_user_id, body, sent_at) FROM 'Messages.csv' WITH DELIMITER ',' NULL '' CSV;
SELECT setval(pg_get_serial_sequence('messages','message_id'), COALESCE((SELECT MAX(message_id)+1 FROM messages), 1), false);

-- Coupons
\COPY coupons(id, code, discount_percent, expiration_time, product_id, category_id) FROM 'Coupons.csv' WITH DELIMITER ',' NULL '' CSV FORCE NULL product_id, category_id;
SELECT setval(pg_get_serial_sequence('coupons','id'), COALESCE((SELECT MAX(id)+1 FROM coupons), 1), false);


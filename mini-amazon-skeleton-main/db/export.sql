-- Export all tables to CSV files in the generate folder
-- Run this with: psql -d database_name -f export.sql

-- Users
\COPY users TO 'generate/Users.csv' WITH DELIMITER ',' NULL '' CSV;

-- Sellers
\COPY sellers TO 'generate/Sellers.csv' WITH DELIMITER ',' NULL '' CSV;

-- Categories
\COPY categories TO 'generate/Categories.csv' WITH DELIMITER ',' NULL '' CSV;

-- Products
\COPY products TO 'generate/Products.csv' WITH DELIMITER ',' NULL '' CSV;

-- Inventory
\COPY inventory TO 'generate/Inventory.csv' WITH DELIMITER ',' NULL '' CSV;

-- Cart items
\COPY cart_items TO 'generate/CartItems.csv' WITH DELIMITER ',' NULL '' CSV;

-- Orders
\COPY orders TO 'generate/Orders.csv' WITH DELIMITER ',' NULL '' CSV;

-- Order items
\COPY order_items TO 'generate/OrderItems.csv' WITH DELIMITER ',' NULL '' CSV;

-- Order sellers
\COPY order_sellers TO 'generate/OrderSellers.csv' WITH DELIMITER ',' NULL '' CSV;

-- Product reviews
\COPY product_reviews TO 'generate/ProductReviews.csv' WITH DELIMITER ',' NULL '' CSV;

-- Seller reviews
\COPY seller_reviews TO 'generate/SellerReviews.csv' WITH DELIMITER ',' NULL '' CSV;

-- Review helpful votes
\COPY review_helpful_votes TO 'generate/ReviewHelpfulVotes.csv' WITH DELIMITER ',' NULL '' CSV;

-- Message threads
\COPY message_threads TO 'generate/MessageThreads.csv' WITH DELIMITER ',' NULL '' CSV;

-- Messages
\COPY messages TO 'generate/Messages.csv' WITH DELIMITER ',' NULL '' CSV;

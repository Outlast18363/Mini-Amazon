from flask import current_app as app


class Product:
    def __init__(self, id, name, description=None, image_url=None, avg_price=None, seller_count=None,
                 avg_rating=None, review_count=None, category_id=None, category_name=None,
                 available=True, created_by=None):
        self.id = id
        self.name = name
        self.description = description
        self.image_url = image_url
        self.avg_price = avg_price
        self.seller_count = seller_count
        self.avg_rating = avg_rating
        self.review_count = review_count
        self.category_id = category_id      
        self.category_name = category_name
        self.available = available
        self.created_by = created_by

    #helper method for get_verbose, get_all, and search_filter_sort
    @staticmethod
    def row_to_product(row):
        return Product(
            id=row[0],
            name=row[1],
            description=row[2],
            image_url=row[3],
            avg_price=float(row[4]) if row[4] is not None else 0.0,
            seller_count=int(row[5]) if row[5] is not None else 0,
            avg_rating=float(row[6]) if row[6] is not None else 0.0,
            review_count=int(row[7]) if row[7] is not None else 0,
            category_id=row[8],
            category_name=row[9],
            created_by=row[10]
        )


    @staticmethod
    def get(id):
        rows = app.db.execute('''
SELECT id, name, category_id
FROM Products
WHERE id = :id
''', id=id)
        if not rows:
            return None
        row = rows[0]
        return Product(
            id=row[0],
            name=row[1],
            category_id=row[2],
        )

    @staticmethod
    def get_verbose(id):
        rows = app.db.execute('''
SELECT
    p.id,
    p.name,
    p.description,
    p.image_url,
    COALESCE(AVG(i.price_cents)/100.0, 0) AS avg_price,
    COUNT(DISTINCT i.seller_id) AS seller_count,
    COALESCE(AVG(r.rating), 0) AS avg_rating,
    COUNT(r.review_id) AS review_count,
    p.category_id,
    c.name AS category_name,
    p.created_by
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN inventory i ON p.id = i.product_id
LEFT JOIN product_reviews r ON p.id = r.product_id
WHERE p.id = :id
GROUP BY p.id, p.name, p.description, p.image_url, p.category_id, c.name, p.created_by
''', id=id)

        if not rows:
            return None
        return Product.row_to_product(rows[0])

    @staticmethod
    def get_all(available=True):
        rows = app.db.execute('''
SELECT
    p.id,
    p.name,
    p.description,
    p.image_url,
    COALESCE(AVG(i.price_cents)/100.0, 0) AS avg_price,
    COUNT(DISTINCT i.seller_id) AS seller_count,
    COALESCE(AVG(r.rating), 0) AS avg_rating,
    COUNT(r.review_id) AS review_count,
    p.category_id,
    c.name AS category_name,
    p.created_by
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN inventory i ON p.id = i.product_id
LEFT JOIN product_reviews r ON p.id = r.product_id
GROUP BY p.id, p.name, p.description, p.image_url, p.category_id, c.name, p.created_by
''')

        return [Product.row_to_product(row) for row in rows]

    @staticmethod
    def search_filter_sort(category=None, search=None, sort=None, limit=None):
        query = '''
SELECT
    p.id,
    p.name,
    p.description,
    p.image_url,
    COALESCE(AVG(i.price_cents)/100.0, 0) AS avg_price,
    COUNT(DISTINCT i.seller_id) AS seller_count,
    COALESCE(AVG(r.rating), 0) AS avg_rating,
    COUNT(r.review_id) AS review_count,
    p.category_id,
    c.name AS category_name,
    p.created_by
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN inventory i ON p.id = i.product_id
LEFT JOIN product_reviews r ON p.id = r.product_id
WHERE 1=1
'''
        params = {}

        if category:
            query += ' AND p.category_id = :category'
            params['category'] = category

        if search:
            query += ' AND (LOWER(p.name) LIKE LOWER(:search) OR LOWER(p.description) LIKE LOWER(:search))'
            params['search'] = f'%{search}%'

        query += '''
GROUP BY p.id, p.name, p.description, p.image_url, p.category_id, c.name, p.created_by
'''

        if sort == 'price_asc':
            query += ' ORDER BY avg_price ASC'
        elif sort == 'price_desc':
            query += ' ORDER BY avg_price DESC'
        elif sort == 'rating_desc':
            query += ' ORDER BY avg_rating DESC'
        else:
            query += ' ORDER BY p.name'

        if limit:
            query += ' LIMIT :limit'
            params['limit'] = limit

        rows = app.db.execute(query, **params)
        return [Product.row_to_product(row) for row in rows]

    @staticmethod
    def create(name, description, created_by, image_url=None, category_id=None):
        rows = app.db.execute('''
INSERT INTO products (name, description, image_url, category_id, created_by)
VALUES (:name, :description, :image_url, :category_id, :created_by)
RETURNING id
''',
                              name=name,
                              description=description,
                              image_url=image_url,
                              category_id=category_id,
                              created_by=created_by)
        return rows[0][0] if rows else None

    @staticmethod
    def update(product_id, name, description, image_url=None, category_id=None):
        rows = app.db.execute('''
UPDATE products
SET name = :name,
    description = :description,
    image_url = :image_url,
    category_id = :category_id
WHERE id = :product_id
RETURNING id
''',
                              product_id=product_id,
                              name=name,
                              description=description,
                              image_url=image_url,
                              category_id=category_id)
        return rows[0][0] if rows else None

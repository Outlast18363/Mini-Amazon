from flask import current_app as app


class ProductReview:
    def __init__(self, review_id: int, product_id: int, author_user_id: int, rating: int, title: str | None, body: str | None, created_at, updated_at):
        self.review_id = review_id
        self.product_id = product_id
        self.author_user_id = author_user_id
        self.rating = rating
        self.title = title
        self.body = body
        self.created_at = created_at
        self.updated_at = updated_at

    @staticmethod
    def for_product(product_id: int):
        rows = app.db.execute('''
SELECT review_id, product_id, author_user_id, rating, title, body, created_at, updated_at
FROM product_reviews WHERE product_id = :product_id ORDER BY created_at DESC
''', product_id=product_id)
        return [ProductReview(*row) for row in rows]

    @staticmethod
    def for_user(user_id: int):
        rows = app.db.execute('''
SELECT review_id, product_id, author_user_id, rating, title, body, created_at, updated_at
FROM product_reviews WHERE author_user_id = :user_id ORDER BY created_at DESC
''', user_id=user_id)
        return [ProductReview(*row) for row in rows]

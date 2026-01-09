from flask import current_app as app


class SellerReview:
    def __init__(self, review_id: int, seller_user_id: int, author_user_id: int, rating: int, title: str | None, body: str | None, created_at, updated_at):
        self.review_id = review_id
        self.seller_user_id = seller_user_id
        self.author_user_id = author_user_id
        self.rating = rating
        self.title = title
        self.body = body
        self.created_at = created_at
        self.updated_at = updated_at

    @staticmethod
    def for_seller(seller_user_id: int):
        rows = app.db.execute('''
SELECT review_id, seller_user_id, author_user_id, rating, title, body, created_at, updated_at
FROM seller_reviews WHERE seller_user_id = :sid ORDER BY created_at DESC
''', sid=seller_user_id)
        return [SellerReview(*row) for row in rows]

    @staticmethod
    def for_user(user_id: int):
        rows = app.db.execute('''
SELECT review_id, seller_user_id, author_user_id, rating, title, body, created_at, updated_at
FROM seller_reviews WHERE author_user_id = :uid ORDER BY created_at DESC
''', uid=user_id)
        return [SellerReview(*row) for row in rows]



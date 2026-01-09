from flask import current_app as app


class Seller:
    def __init__(self, id: int, user_id: int):
        self.id = id
        self.user_id = user_id

    @staticmethod
    def is_user_seller(user_id: int) -> bool:
        rows = app.db.execute('''
SELECT 1 FROM sellers WHERE user_id = :user_id
''', user_id=user_id)
        return len(rows) > 0

    @staticmethod
    def get_by_user_id(user_id: int):
        rows = app.db.execute('''
SELECT id, user_id FROM sellers WHERE user_id = :user_id
''', user_id=user_id)
        return Seller(*rows[0]) if rows else None

    @staticmethod
    def get(id: int):
        rows = app.db.execute('''
SELECT id, user_id FROM sellers WHERE id = :id
''', id=id)
        return Seller(*rows[0]) if rows else None

    @staticmethod
    def become_seller(user_id: int):
        if not Seller.is_user_seller(user_id):
            app.db.execute('''
INSERT INTO sellers (user_id) VALUES (:user_id)
''', user_id=user_id)
            return True
        return False

    # Note: deleting a seller deletes their inventory as well
    @staticmethod
    def remove_seller(user_id: int):
        seller = Seller.get_by_user_id(user_id)
        if seller:
            app.db.execute('''
DELETE FROM inventory WHERE seller_id = :seller_id
''', seller_id=seller.id)

            app.db.execute('''
DELETE FROM sellers WHERE id = :seller_id
''', seller_id=seller.id)
            return True
        return False

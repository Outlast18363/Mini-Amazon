from flask import current_app as app


class Transaction:
    def __init__(self, id: int, user_id: int, amount, order_id: int | None, created_at):
        self.id = id
        self.user_id = user_id
        self.amount = amount
        self.order_id = order_id
        self.created_at = created_at

    @staticmethod
    def for_user(user_id: int):
        rows = app.db.execute('''
SELECT id, user_id, amount, order_id, created_at FROM transactions
WHERE user_id = :user_id ORDER BY created_at DESC
''', user_id=user_id)
        return [Transaction(*row) for row in rows]



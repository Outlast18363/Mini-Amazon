from flask import current_app as app


class MessageThread:
    def __init__(self, thread_id: int, order_id: int, seller_user_id: int, buyer_user_id: int, created_at):
        self.thread_id = thread_id
        self.order_id = order_id
        self.seller_user_id = seller_user_id
        self.buyer_user_id = buyer_user_id
        self.created_at = created_at

    @staticmethod
    def for_user(user_id: int):
        rows = app.db.execute('''
SELECT thread_id, order_id, seller_user_id, buyer_user_id, created_at
FROM message_threads WHERE seller_user_id = :uid OR buyer_user_id = :uid
ORDER BY created_at DESC
''', uid=user_id)
        return [MessageThread(*row) for row in rows]



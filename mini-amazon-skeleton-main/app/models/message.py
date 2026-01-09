from flask import current_app as app


class Message:
    def __init__(self, message_id: int, thread_id: int, sender_user_id: int, body: str, sent_at):
        self.message_id = message_id
        self.thread_id = thread_id
        self.sender_user_id = sender_user_id
        self.body = body
        self.sent_at = sent_at

    @staticmethod
    def for_thread(thread_id: int):
        rows = app.db.execute('''
SELECT message_id, thread_id, sender_user_id, body, sent_at
FROM messages WHERE thread_id = :tid ORDER BY sent_at ASC
''', tid=thread_id)
        return [Message(*row) for row in rows]



from flask import current_app as app


class Category:
    def __init__(self, id: int, name: str, parent_id: int | None):
        self.id = id
        self.name = name
        self.parent_id = parent_id

    @staticmethod
    def all():
        rows = app.db.execute('''
SELECT id, name, parent_id FROM categories ORDER BY name
''')
        return [Category(*row) for row in rows]

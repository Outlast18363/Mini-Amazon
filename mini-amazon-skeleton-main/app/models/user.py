from flask_login import UserMixin
from flask import current_app as app
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

from .. import login


class User(UserMixin):
    def __init__(self, id, email, full_name, address, balance):
        self.id = id
        self.email = email
        self.full_name = full_name
        self.address = address
        self.balance = balance

    # ==============
    # Auth helpers
    # ==============

    @staticmethod
    def get_by_auth(email, password):
        """
        Given email + plain password from login form:
        - look up the row,
        - check password_hash with check_password_hash,
        - if ok, return a User object.
        Otherwise return None.
        """
        rows = app.db.execute("""
            SELECT password_hash,
                   id, email, full_name, address, balance
            FROM users
            WHERE email = :email
        """,
        email=email)

        if not rows:
            # no such email
            return None

        stored_hash = rows[0][0]
        if not check_password_hash(stored_hash, password):
            # wrong password
            return None

        # rows[0] is (password_hash, id, email, full_name, address, balance)
        return User(*(rows[0][1:]))

    @staticmethod
    def email_exists(email):
        """
        Check if any user already has this email.
        Used by RegistrationForm validator.
        """
        rows = app.db.execute("""
            SELECT 1
            FROM users
            WHERE email = :email
        """,
        email=email)
        return len(rows) > 0

    @staticmethod
    def email_taken_by_other(current_user_id, new_email):
        """
        Check if another user (NOT me) already uses this email.
        Used by AccountUpdateForm validator.
        """
        rows = app.db.execute("""
            SELECT 1
            FROM users
            WHERE email = :email
              AND id <> :me
            LIMIT 1
        """,
        email=new_email,
        me=current_user_id)
        return len(rows) > 0

    @staticmethod
    def register(email, password, full_name, address):
        """
        Create a new user.
        We hash the password, start balance at 0.
        Returns a User object on success, or None on failure.
        """
        try:
            rows = app.db.execute("""
                INSERT INTO users(email, full_name, address, password_hash, balance)
                VALUES(:email, :full_name, :address, :password_hash, 0.00)
                RETURNING id
            """,
            email=email,
            full_name=full_name,
            address=address,
            password_hash=generate_password_hash(password))

            new_id = rows[0][0]
            return User.get(new_id)

        except Exception as e:
            # basic fallback error logging
            print("User.register error:", str(e))
            return None

    @staticmethod
    @login.user_loader
    def get(id):
        """
        Loader used by flask-login. Also callable directly.
        Returns a User object (id, email, full_name, address, balance)
        or None if not found.
        """
        rows = app.db.execute("""
            SELECT id, email, full_name, address, balance
            FROM users
            WHERE id = :id
        """,
        id=id)

        return User(*(rows[0])) if rows else None

    # ==============
    # Account / profile helpers
    # ==============

    @staticmethod
    def get_by_id(user_id):
        """
        Return a dict with keys:
        id, email, full_name, address, balance
        so that views can do info['full_name'], etc.
        """
        rows = app.db.execute("""
            SELECT id,
                   email,
                   full_name,
                   address,
                   balance
            FROM users
            WHERE id = :uid
        """,
        uid=user_id)

        if not rows:
            return None

        # rows[0] is a tuple like (id, email, full_name, address, balance)
        row = rows[0]
        return {
            'id': row[0],
            'email': row[1],
            'full_name': row[2],
            'address': row[3],
            'balance': row[4],
        }

    @staticmethod
    def update_profile(user_id, full_name, address, email, new_password_or_none):
        """
        Update profile fields for this user.
        - full_name
        - address
        - email
        - optional new password (raw)
        We do NOT change id or balance here.
        """

        # Check if email is already taken by another user
        rows = app.db.execute("""
            SELECT id FROM users WHERE email = :email AND id != :uid
        """, email=email, uid=user_id)
        if rows:
            return False, "Email already in use."

        # Case 1: update password as well
        if new_password_or_none and new_password_or_none.strip() != "":
            app.db.execute("""
                UPDATE users
                SET full_name     = :full_name,
                    address       = :address,
                    email         = :email,
                    password_hash = :pw_hash
                WHERE id = :uid
            """,
            uid=user_id,
            full_name=full_name,
            address=address,
            email=email,
            pw_hash=generate_password_hash(new_password_or_none))

        else:
            # Case 2: do NOT change password
            app.db.execute("""
                UPDATE users
                SET full_name = :full_name,
                    address   = :address,
                    email     = :email
                WHERE id = :uid
            """,
            uid=user_id,
            full_name=full_name,
            address=address,
            email=email)

        return True, None

    # ==============
    # (optional future work)
    # Balance helpers for /balance page
    # ==============

    @staticmethod
    def get_balance(user_id):
        """
        Helper for a future /balance page.
        """
        rows = app.db.execute("""
            SELECT balance
            FROM users
            WHERE id = :uid
        """,
        uid=user_id)
        return rows[0][0] if rows else 0.00

    @staticmethod
    def add_balance(user_id, amount_delta):
        """
        Increase balance by amount_delta (positive for top-up, negative for withdraw).
        NOTE: you should check in route that withdraw does not go below zero.
        """
        with app.db.engine.begin() as conn:
            conn.execute(text("""
                UPDATE users
                SET balance = balance + :amt
                WHERE id = :uid
            """), dict(uid=user_id, amt=amount_delta))

            conn.execute(text("""
                INSERT INTO transactions(user_id, amount)
                VALUES(:uid, :amt)
            """), dict(uid=user_id, amt=amount_delta))

        return True

    @staticmethod
    def search(keyword):
        """
        Search for users by ID (if keyword is int) or full_name (partial match).
        """
        try:
            uid = int(keyword)
            # If it's an integer, search by ID first
            rows = app.db.execute("""
                SELECT id, email, full_name, address, balance
                FROM users
                WHERE id = :uid
            """, uid=uid)
            if rows:
                return [User(*row) for row in rows]
        except ValueError:
            pass
        
        # Search by full_name or email
        rows = app.db.execute("""
            SELECT id, email, full_name, address, balance
            FROM users
            WHERE LOWER(full_name) LIKE LOWER(:keyword)
               OR LOWER(email) LIKE LOWER(:keyword)
        """, keyword=f'%{keyword}%')
        
        return [User(*row) for row in rows]

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    def __init__(self, user_id, name, email, password_plain, is_developer=False):
        self.id = user_id
        self.name = name
        self.email = email
        self.password_hash = generate_password_hash(password_plain)
        self._is_developer = is_developer

    @property
    def is_developer(self):
        """
        Determines if the user has developer access.
        """
        return self._is_developer

    def check_password(self, password):
        """
        Validates the password hash.
        """
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"

# Hardcoded in-memory users list
USERS_BY_ID = {
    1: User(1, "SNIST Admin", "admin@sreenidhi.edu.in", "Admin@SNIST123", is_developer=False),
    2: User(2, "SNIST Developer", "developer@sreenidhi.edu.in", "Dev@SNIST123", is_developer=True)
}

USERS_BY_EMAIL = {user.email: user for user in USERS_BY_ID.values()}

def get_user_by_id(user_id):
    """
    Looks up a user by ID in-memory.
    """
    try:
        return USERS_BY_ID.get(int(user_id))
    except (ValueError, TypeError):
        return None

def get_user_by_email(email):
    """
    Looks up a user by email in-memory.
    """
    if not email:
        return None
    return USERS_BY_EMAIL.get(email.strip().lower())

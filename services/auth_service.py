from models.user import get_user_by_id, get_user_by_email

class AuthService:
    @staticmethod
    def authenticate_user(email, password):
        """
        Verifies credentials of an admin or developer user.
        Returns the User object if successful, else None.
        """
        user = get_user_by_email(email)
        if user and user.check_password(password):
            return user
        return None

    @staticmethod
    def get_user_by_id(user_id):
        return get_user_by_id(user_id)

    @staticmethod
    def get_user_by_email(email):
        return get_user_by_email(email)

    @staticmethod
    def change_password(user_id, current_password, new_password):
        """
        Changes user's password in memory if the current password is valid.
        """
        user = get_user_by_id(user_id)
        if user and user.check_password(current_password):
            from werkzeug.security import generate_password_hash
            user.password_hash = generate_password_hash(new_password)
            return True
        return False

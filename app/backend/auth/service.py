"""Authentication helpers: the Flask-Login user object."""
from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = str(id)
        self.username = username
        self.role = role

"""
Authentication helpers for QuizWeaver web frontend.
"""

from werkzeug.security import check_password_hash, generate_password_hash

from src.database import User


def create_user(session, username, password, display_name=None, role="teacher"):
    """Create a new user with hashed password.

    Args:
        session: SQLAlchemy session.
        username: Unique username.
        password: Plain-text password (will be hashed).
        display_name: Optional display name.
        role: User role (default "teacher").

    Returns:
        User object on success, None if username already exists.
    """
    existing = session.query(User).filter_by(username=username).first()
    if existing:
        return None

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        display_name=display_name or username,
        role=role,
    )
    session.add(user)
    session.commit()
    return user


def authenticate_user(session, username, password):
    """Authenticate a user by username and password.

    Args:
        session: SQLAlchemy session.
        username: Username to look up.
        password: Plain-text password to verify.

    Returns:
        User object if credentials are valid, None otherwise.
    """
    user = session.query(User).filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        return user
    return None


def change_password(session, user_id, old_password, new_password):
    """Change a user's password.

    Args:
        session: SQLAlchemy session.
        user_id: ID of the user.
        old_password: Current password for verification.
        new_password: New password to set.

    Returns:
        True if password was changed, False if old password is wrong or user not found.
    """
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return False
    if not check_password_hash(user.password_hash, old_password):
        return False
    user.password_hash = generate_password_hash(new_password)
    session.commit()
    return True


def get_user_count(session):
    """Return the total number of users in the database."""
    return session.query(User).count()


def get_user_by_id(session, user_id):
    """Get a user by their ID.

    Returns:
        User object or None.
    """
    return session.query(User).filter_by(id=user_id).first()

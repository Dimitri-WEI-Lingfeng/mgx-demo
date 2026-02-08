"""Database dependencies."""
from mgx_api.dao import SessionDAO


def get_session_dao() -> SessionDAO:
    """
    Get SessionDAO instance.
    
    Returns:
        SessionDAO instance
    """
    return SessionDAO()

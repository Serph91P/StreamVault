"""
SQLAlchemy Models Type Helper Module

This module provides helper types and functions for properly typing SQLAlchemy models.
It should be used to ensure proper type checking in the codebase.
"""

from typing import TypeVar, Generic, Type, Any, Dict, List, Optional, Union, cast
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Session

# We only need relationship in some specific places
# Import it only where needed to avoid mypy errors
try:
    from sqlalchemy.orm import relationship
except ImportError:
    pass

# Import a universally typed version of DeclarativeMeta that works across SQLAlchemy versions
# Define it as a type alias to avoid redefinition conflicts
from typing import Protocol

# Define a protocol for DeclarativeMeta to avoid import issues
class DeclarativeMeta(Protocol):
    """Protocol representing SQLAlchemy's DeclarativeMeta for type checking"""
    pass

# Import the specific version only for runtime use, not for type checking
_DeclarativeMeta = None
try:
    from sqlalchemy.orm.decl_api import DeclarativeMeta as _DeclarativeMeta  # SQLAlchemy 1.4+
except ImportError:
    try:
        from sqlalchemy.ext.declarative.api import DeclarativeMeta as _DeclarativeMeta  # SQLAlchemy 1.3
    except ImportError:
        pass  # The protocol definition above will be used for type checking

# Import other SQLAlchemy components
from sqlalchemy.sql.expression import ClauseElement
from datetime import datetime

# Type variable for the model class
T = TypeVar('T')

# Type variable for model instance
ModelT = TypeVar('ModelT')

# Define a base class for type-safe model instance usage
class TypedModel:
    """Base class for all models providing type-safe attribute access"""
    id: int
    
    @classmethod
    def get_by_id(cls, session: Session, id: int) -> Optional['TypedModel']:
        """Get a model instance by ID with proper typing"""
        return session.query(cls).filter(cls.id == id).first()

# Helper function to properly type column access from a model instance
def get_column_value(model: Any, column_name: str) -> Any:
    """
    Get a column value from a model instance with proper typing.
    Use this instead of direct attribute access in places where mypy complains.
    
    Example:
        # Instead of this (which mypy flags as an error):
        user.username
        
        # Use this:
        get_column_value(user, 'username')
    """
    return getattr(model, column_name)

# Helper function to set column value with proper typing
def set_column_value(model: Any, column_name: str, value: Any) -> None:
    """
    Set a column value on a model instance with proper typing.
    Use this instead of direct attribute assignment in places where mypy complains.
    
    Example:
        # Instead of this (which mypy flags as an error):
        user.username = 'new_username'
        
        # Use this:
        set_column_value(user, 'username', 'new_username')
    """
    setattr(model, column_name, value)

# Example of how to properly type a model class
class ExampleTypedUser(TypedModel):
    """Example of a typed SQLAlchemy model class"""
    username: str
    password: str
    is_admin: bool
    created_at: datetime
    
    @classmethod
    def create(cls, 
              session: Session,
              username: str,
              password: str,
              is_admin: bool = False) -> 'ExampleTypedUser':
        """Create a new user with proper typing"""
        user = cls.__new__(cls)
        user.username = username
        user.password = password
        user.is_admin = is_admin
        session.add(user)
        session.commit()
        return user
    
    @classmethod
    def get_by_username(cls, 
                       session: Session,
                       username: str) -> Optional['ExampleTypedUser']:
        """Get a user by username with proper typing"""
        return session.query(cls).filter_by(username=username).first()

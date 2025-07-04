"""
SQLAlchemy Models Type Helper Module

This module provides helper types and functions for properly typing SQLAlchemy models.
It should be used to ensure proper type checking in the codebase.
"""

from typing import TypeVar, Generic, Type, Any, Dict, List, Optional, Union, cast
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Session, relationship, DeclarativeMeta
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
        user = cls()  # type: ignore
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
        return session.query(cls).filter(cls.username == username).first()  # type: ignore

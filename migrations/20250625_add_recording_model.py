"""
Migration to add the Recording model table to the database.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Define model to match app.models.Recording
class Recording(Base):
    __tablename__ = "recordings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False)  # "recording", "completed", "error"
    duration = Column(Integer, nullable=True)  # Duration in seconds
    path = Column(String, nullable=True)  # Path to the recording file

def upgrade(engine):
    """
    Create the recordings table.
    """
    Base.metadata.create_all(engine, tables=[Recording.__table__])

def downgrade(engine):
    """
    Drop the recordings table.
    """
    engine.execute(text("DROP TABLE IF EXISTS recordings;"))

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.sql import func
from datetime import datetime

# Base class that tracks all database models
class Base(DeclarativeBase):
    pass

class Contact(Base):
    __tablename__ = "contacts"

    # Mapped[] defines Python types, mapped_column() defines DB constraints
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Indexes on unique lookups like email speed up queries drastically
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    
    # Automatically records creation timestamp on the database server level
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

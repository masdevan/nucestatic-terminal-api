from sqlalchemy import Column, String
from app.databases.base import TimestampMixin, IDMixin
from app.databases.config import Base


class User(IDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)

from sqlalchemy import Column, String, Integer
from app.databases.base import IDMixin
from app.databases.config import Base


class Bookmark(IDMixin, Base):
    __tablename__ = "bookmarks"

    user_id = Column(Integer, nullable=False, index=True)
    symbol = Column(String(50), nullable=False)
    server = Column(String(50), nullable=False)
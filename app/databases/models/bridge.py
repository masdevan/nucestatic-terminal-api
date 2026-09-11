from sqlalchemy import Column, String, Boolean
from app.databases.base import IDMixin
from app.databases.config import Base


class BridgeApi(IDMixin, Base):
    __tablename__ = "bridge_apis"

    name = Column(String(100), nullable=False)
    url = Column(String(255), unique=True, nullable=False, index=True)
    active = Column(Boolean, nullable=False, default=False)
    mode = Column(String(10), nullable=False, default="static")
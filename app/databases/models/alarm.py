from sqlalchemy import Column, String, Integer, Text, Numeric, Boolean
from app.databases.base import IDMixin, TimestampMixin
from app.databases.config import Base


class Alarm(IDMixin, TimestampMixin, Base):
    __tablename__ = "alarms"

    user_id = Column(Integer, nullable=False, index=True)
    symbol = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    entry_type = Column(String(4), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    tp_price = Column(Numeric(20, 8), nullable=True)
    sl_price = Column(Numeric(20, 8), nullable=True)
    timeframe = Column(String(10), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    webhook_url = Column(String(255), nullable=True)
from sqlalchemy import Column, String, DateTime, text
from sqlalchemy.dialects.postgresql import ARRAY
from app.models.base import Base


class PropertyDefinition(Base):
    __tablename__ = 'property_definition'

    code = Column(String(50), primary_key=True)
    label = Column(String(100), nullable=False)
    unit = Column(String(20))
    data_type = Column(String(20), nullable=False)
    applies_to = Column(ARRAY(String()), nullable=False)
    category = Column(String(50))
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base, engine

# ✅ Subscription (OK)
class Subscription(Base):
    __tablename__ = 'subscriptions'
    __table_args__ = {'extend_existing': True}
    device_id = Column(String, primary_key=True, index=True)
    phone_number = Column(String, nullable=False)
    months = Column(Integer, default=1)
    activation_key = Column(String, unique=True, index=True)
    status = Column(String, default="pending")
    created = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    client = relationship("Client", back_populates="subscriptions", uselist=False)

# ✅ Admin (OK)
class Admin(Base):
    __tablename__ = "admins"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone = Column(String, unique=True, index=True)
    password = Column(String)
    created_at = Column(DateTime, server_default=func.now())

# ✅ Client (simplifié + lien Subscription)
class Client(Base):
    __tablename__ = "clients"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True, index=True)
    phone = Column(String, index=True, unique=True)
    device_id = Column(String, ForeignKey("subscriptions.device_id"), unique=True)
    subscriptions = relationship("Subscription", back_populates="client")
    validations = relationship("ValidationLog", back_populates="client")

# ✅ ValidationLog UNIQUE (fusion des 2)
class ValidationLog(Base):
    __tablename__ = "validation_logs"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    # Liens multiples possibles
    device_id = Column(String, ForeignKey('subscriptions.device_id'), index=True)
    client_id = Column(Integer, ForeignKey('clients.id'), index=True)
    client_phone = Column(String, index=True)
    
    # Infos validation
    admin_id = Column(Integer, ForeignKey('admins.id'))
    admin_name = Column(String)
    months = Column(Integer)
    activation_key = Column(String)
    status = Column(String, default="validated")
    expires_at = Column(DateTime)
    validated_at = Column(DateTime, server_default=func.now())
    
    # Relations
    client = relationship("Client", back_populates="validations")

def create_tables():
    Base.metadata.create_all(bind=engine)

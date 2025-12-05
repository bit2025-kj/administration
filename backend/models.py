from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base
from database import engine


# ✅ UNE SEULE FOIS Subscription (avec extend_existing=True)
class Subscription(Base):
    __tablename__ = 'subscriptions'
    __table_args__ = {'extend_existing': True}  # ✅ FIX DUPLICATA
    
    device_id = Column(String, primary_key=True, index=True)
    phone_number = Column(String, nullable=False)
    months = Column(Integer, default=1)
    activation_key = Column(String, unique=True, index=True)
    status = Column(String, default="pending")
    created = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)

# ✅ UNE SEULE FOIS Admin
class Admin(Base):
    __tablename__ = "admins"
    __table_args__ = {'extend_existing': True}  # ✅ FIX DUPLICATA
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone = Column(String, unique=True, index=True)
    password = Column(String)
    created_at = Column(DateTime, server_default=func.now())

# ✅ NOUVELLE TABLE ValidationLog (historique)
class ValidationLog(Base):
    __tablename__ = "validation_logs"
    __table_args__ = {'extend_existing': True}  # ✅ Sécurité
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey('subscriptions.device_id'), index=True)
    client_phone = Column(String, index=True)
    months = Column(Integer)
    activation_key = Column(String)
    admin_id = Column(Integer, ForeignKey('admins.id'))
    admin_name = Column(String)
    validated_at = Column(DateTime, server_default=func.now())

# ✅ AJOUTEZ à la fin models.py :
def create_tables():
    Base.metadata.create_all(bind=engine)

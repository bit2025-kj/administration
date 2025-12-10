from sqlalchemy.orm import Session
from backend import models
from backend.models import Subscription, Admin, ValidationLog, Client
from datetime import datetime, timedelta
import bcrypt
from uuid import uuid4

def get_subscription_by_device(db: Session, device_id: str):
    return db.query(models.Subscription).filter(models.Subscription.device_id == device_id).first()

def create_subscription(db: Session, device_id: str, phone: str, months: int):
    activation_key = str(uuid4()).replace('-', '')[:10]
    sub = models.Subscription(
        device_id=device_id, phone_number=phone, months=months,
        activation_key=activation_key, status="pending"
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub

# ✅ VALIDATION CORRIGÉE : Client + NOM + Log complet
def validate_subscription(db: Session, device_id: str, admin_id: int = None, admin_name: str = "Admin") -> bool:
    sub = get_subscription_by_device(db, device_id)
    if sub and sub.status == "pending":
        # ✅ 1. Créer Client AVEC NOM (fallback téléphone)
        client = db.query(Client).filter(Client.device_id == device_id).first()
        if not client:
            client_name = getattr(sub, 'client_name', sub.phone_number)  # ✅ Nom ou téléphone
            client = Client(device_id=device_id, phone=sub.phone_number, name=client_name)
            db.add(client)
            db.commit()
            db.refresh(client)
            print(f"👤 CLIENT CRÉÉ: {client.name}")
        
        # ✅ 2. Valider subscription
        sub.status = "validated"
        sub.expires_at = datetime.utcnow() + timedelta(days=30 * sub.months)
        db.commit()
        db.refresh(sub)
        
        # ✅ 3. Log HISTORIQUE complet
        log_validation(db, device_id, sub.phone_number, sub.months, 
                      sub.activation_key, admin_id, admin_name, sub.expires_at)
        print(f"✅ VALIDÉ + LOG: {device_id} | {admin_name}")
        return True
    print(f"❌ KO: {device_id}")
    return False

def log_validation(db: Session, device_id: str, client_phone: str, months: int, 
                  activation_key: str, admin_id: int = None, admin_name: str = "Admin", 
                  expires_at: datetime = None):
    log = models.ValidationLog(
        device_id=device_id, 
        client_phone=client_phone, 
        months=months,
        activation_key=activation_key, 
        admin_id=admin_id, 
        admin_name=admin_name,
        expires_at=expires_at or datetime.utcnow() + timedelta(days=30 * months),
        validated_at=datetime.utcnow()
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

# RESTE IDENTIQUE (OK)
def get_pending_requests(db: Session):
    return db.query(models.Subscription).filter(models.Subscription.status == "pending").all()

def get_admin_by_phone(db: Session, phone: str):
    return db.query(models.Admin).filter(models.Admin.phone == phone).first()

def create_admin(db: Session, name: str, phone: str, password: str):
    total_admins = db.query(models.Admin).count()
    if total_admins >= 6: return None
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    admin = models.Admin(name=name, phone=phone, password=hashed.decode('utf-8'))
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin

def authenticate_admin(db: Session, phone: str, password: str):
    admin = get_admin_by_phone(db, phone)
    if admin and bcrypt.checkpw(password.encode('utf-8'), admin.password.encode('utf-8')):
        return admin
    return None

def get_validation_history(db: Session, limit: int = 50):
    return db.query(models.ValidationLog).order_by(
        models.ValidationLog.validated_at.desc()
    ).limit(limit).all()

def get_client_history(db: Session, device_id: str):
    return db.query(models.ValidationLog).filter(
        models.ValidationLog.device_id == device_id
    ).order_by(models.ValidationLog.validated_at.desc()).all()

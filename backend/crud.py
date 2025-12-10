from sqlalchemy.orm import Session
from backend import models
from backend.models import Subscription, Admin, ValidationLog, Client  # ✅ AJOUT Client
from datetime import datetime, timedelta
import bcrypt
from uuid import uuid4

# ✅ VOS FONCTIONS EXISTANTES (OK)
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

# ✅ VALIDATE MODIFIÉE : Crée Client + Log automatique
def validate_subscription(db: Session, device_id: str, admin_id: int = None, admin_name: str = "Admin") -> bool:
    sub = get_subscription_by_device(db, device_id)
    if sub and sub.status == "pending":
        # ✅ 1. Créer Client auto
        client = db.query(Client).filter(Client.device_id == device_id).first()
        if not client:
            client = Client(device_id=device_id, phone=sub.phone_number)
            db.add(client)
            db.commit()
            db.refresh(client)
        
        # ✅ 2. Valider subscription
        sub.status = "validated"
        sub.expires_at = datetime.utcnow() + timedelta(days=30 * sub.months)
        db.commit()
        
        # ✅ 3. Logger validation HISTORIQUE
        log_validation(db, device_id, sub.phone_number, sub.months, 
                      sub.activation_key, admin_id, admin_name)
        print(f"✅ VALIDÉ + LOG: {device_id} par {admin_name}")
        return True
    return False

def get_pending_requests(db: Session):
    return db.query(models.Subscription).filter(models.Subscription.status == "pending").all()

# ✅ ADMIN CRUD (OK)
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

# ✅ HISTORIQUE (OK + CORRIGÉ)
def log_validation(db: Session, device_id: str, client_phone: str, months: int, 
                  activation_key: str, admin_id: int = None, admin_name: str = "Admin"):
    log = models.ValidationLog(
        device_id=device_id, client_phone=client_phone, months=months,
        activation_key=activation_key, admin_id=admin_id, admin_name=admin_name
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

def get_validation_history(db: Session, limit: int = 50):
    return db.query(models.ValidationLog).order_by(
        models.ValidationLog.validated_at.desc()
    ).limit(limit).all()

def get_client_history(db: Session, device_id: str):  # ✅ NOUVEAU : Par device_id
    return db.query(models.ValidationLog).filter(
        models.ValidationLog.device_id == device_id
    ).order_by(models.ValidationLog.validated_at.desc()).all()

# ✅ CLIENT CRUD (CORRIGÉ)
def create_or_get_client(db: Session, device_id: str, phone: str):
    client = db.query(models.Client).filter(models.Client.device_id == device_id).first()
    if not client:
        client = models.Client(device_id=device_id, phone=phone)
        db.add(client)
        db.commit()
        db.refresh(client)
    return client

def get_client_validations(db: Session, client_id: int):  # ✅ CORRIGÉ
    return db.query(models.ValidationLog).filter(
        models.ValidationLog.client_id == client_id
    ).order_by(models.ValidationLog.validated_at.desc()).all()

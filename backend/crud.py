from sqlalchemy.orm import Session
from backend import models
from backend.models import Subscription, Admin, ValidationLog

from datetime import datetime, timedelta
import bcrypt
from uuid import uuid4


# ✅ SUBSCRIPTION CRUD (vos fonctions existantes)
def get_subscription_by_device(db: Session, device_id: str):
    """Récupère subscription par device_id"""
    return db.query(models.Subscription).filter(models.Subscription.device_id == device_id).first()

def create_subscription(db: Session, device_id: str, phone: str, months: int):
    """Crée nouvelle demande abonnement"""
    activation_key = str(uuid4()).replace('-', '')[:10]
    sub = models.Subscription(
        device_id=device_id,
        phone_number=phone,
        months=months,
        activation_key=activation_key,
        status="pending",
        created=datetime.utcnow(),
        expires_at=None
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub

def validate_subscription(db: Session, device_id: str):
    """Valide abonnement (admin)"""
    sub = get_subscription_by_device(db, device_id)
    if sub and sub.status == "pending":
        sub.status = "validated"
        sub.expires_at = datetime.utcnow() + timedelta(days=30 * sub.months)
        db.commit()
        return True
    return False

def get_pending_requests(db: Session):
    """Liste toutes demandes en attente"""
    return db.query(models.Subscription).filter(models.Subscription.status == "pending").all()

def get_pending_by_device(db: Session, device_id: str):
    """Récupère pending par device (pour validate)"""
    return db.query(models.Subscription).filter(
        models.Subscription.device_id == device_id,
        models.Subscription.status == "pending"
    ).first()

def clear_all_pending(db: Session):
    """Vide toutes demandes en attente (admin)"""
    pending = db.query(models.Subscription).filter(models.Subscription.status == "pending").all()
    for sub in pending:
        db.delete(sub)
    db.commit()

# ✅ ADMIN CRUD (nouveau)
def get_admin_by_phone(db: Session, phone: str):
    """Récupère admin par téléphone"""
    return db.query(models.Admin).filter(models.Admin.phone == phone).first()

def create_admin(db: Session, name: str, phone: str, password: str):
    """Crée admin (MAX 6)"""
    # Vérif limite 6 admins
    total_admins = db.query(models.Admin).count()
    if total_admins >= 6:
        return None  # Max 6 atteint
    
    # Hash mot de passe
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    admin = models.Admin(
        name=name, 
        phone=phone, 
        password=hashed.decode('utf-8')
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"✅ Admin créé: {name} ({phone})")
    return admin

def authenticate_admin(db: Session, phone: str, password: str):
    """Authentifie admin (bcrypt)"""
    admin = get_admin_by_phone(db, phone)
    if not admin:
        return None
    if bcrypt.checkpw(password.encode('utf-8'), admin.password.encode('utf-8')):
        print(f"✅ Admin connecté: {admin.name}")
        return admin
    return None

# ✅ AJOUTEZ à vos fonctions existantes :

def log_validation(db: Session, device_id: str, client_phone: str, months: int, 
                  activation_key: str, admin_id: int, admin_name: str):
    """Enregistre validation dans historique"""
    log = models.ValidationLog(
        device_id=device_id,
        client_phone=client_phone,
        months=months,
        activation_key=activation_key,
        admin_id=admin_id,
        admin_name=admin_name
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

def get_validation_history(db: Session, limit: int = 50):
    """Historique des 50 dernières validations"""
    return db.query(models.ValidationLog).order_by(
        models.ValidationLog.validated_at.desc()
    ).limit(limit).all()

def get_validations_by_admin(db: Session, admin_phone: str):
    """Validations par admin"""
    admin = get_admin_by_phone(db, admin_phone)
    if not admin:
        return []
    return db.query(models.ValidationLog).filter(
        models.ValidationLog.admin_id == admin.id
    ).order_by(models.ValidationLog.validated_at.desc()).all()
def create_client(db: Session, phone: str):
    client = Client(phone=phone)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client

def get_client_validations(db: Session, client_id: int):
    return db.query(ValidationLog).filter(ValidationLog.client_id == client_id).order_by(ValidationLog.created_at.desc()).all()

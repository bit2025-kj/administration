from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.sql import func
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPBearer
import jwt, os, json, bcrypt
from typing import List

from backend import crud
from backend import models
from backend.database import engine, get_db
from backend.models import create_tables, Client, ValidationLog, Subscription, Admin

app = FastAPI(title="_ap_bar Backend - Admin")

@app.on_event("startup")
async def startup():
    create_tables()

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"]
)

# JWT + WEBSOCKET
SECRET_KEY = os.getenv("SECRET_KEY", "votre_secret_super_secret_ap_bar_2025")
ALGORITHM = "HS256"
security = HTTPBearer()

class ConnectionManager:
    def __init__(self): 
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket): 
        await websocket.accept(); self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket): 
        self.active_connections.remove(websocket)
    async def broadcast(self, message: str): 
        for conn in self.active_connections: 
            await conn.send_text(message)

manager = ConnectionManager()

def get_current_admin(token: str = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        phone = payload.get("phone")
        if phone is None: raise HTTPException(status_code=401, detail="Token invalide")
        return phone
    except jwt.PyJWTError: 
        raise HTTPException(status_code=401, detail="Token invalide")

# ✅ MODÈLES COMPLETS
class SubscriptionRequest(BaseModel):
    device_id: str
    client_name: str          # ✅ NOM CLIENT
    phone_number: str
    months: int

class CheckSubscriptionRequest(BaseModel):
    device_id: str

class AdminLogin(BaseModel):      # ✅ MANQUANT
    phone: str
    password: str

class AdminSignup(BaseModel):     # ✅ MANQUANT
    name: str
    phone: str
    password: str

# MOBILE API
@app.post("/request_subscription")
async def create_subscription(request: SubscriptionRequest, db: Session = Depends(get_db)):
    existing = crud.get_subscription_by_device(db, request.device_id)

    # S'il y a déjà un abonnement, on renvoie toujours la même clé + status
    if existing:
        return {
            "activation_key": existing.activation_key,
            "status": existing.status,
            "expires_at": existing.expires_at.isoformat() if existing.expires_at else None,
        }

    # Sinon, on crée une nouvelle entrée
    sub = crud.create_subscription(db, request.device_id, request.phone_number, request.months)
    await manager.broadcast(json.dumps({
        "type": "new_request",
        "device_id": sub.device_id,
        "client_name": request.client_name,
        "phone": sub.phone_number,
        "key": sub.activation_key,
        "months": sub.months,
        "timestamp": sub.created.isoformat() if sub.created else None,
    }))
    return {"activation_key": sub.activation_key, "status": sub.status}


@app.post("/check_subscription")
async def check_subscription(request: CheckSubscriptionRequest, db: Session = Depends(get_db)):
    print(f"🔍 Flutter check pour: {request.device_id}")
    sub = crud.get_subscription_by_device(db, request.device_id)
    if not sub: 
        print(f"❌ Device {request.device_id} non trouvé")
        return {"error": "Device non trouvé"}
    print(f"📊 Status actuel: {sub.status}")
    return {
        "activation_key": sub.activation_key,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "status": sub.status
    }

# ✅ ADMIN API COMPLÈTE
@app.post("/admin/login")
async def admin_login(login: AdminLogin, db: Session = Depends(get_db)):
    admin = crud.authenticate_admin(db, login.phone, login.password)
    if not admin:
        raise HTTPException(status_code=401, detail="Numéro ou mot de passe incorrect")
    
    token = jwt.encode({
        "phone": admin.phone,
        "name": admin.name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"token": token, "name": admin.name, "phone": admin.phone}

@app.post("/admin/signup")
async def admin_signup(signup: AdminSignup, db: Session = Depends(get_db)):
    existing = crud.get_admin_by_phone(db, signup.phone)
    if existing:
        raise HTTPException(status_code=400, detail="Numéro déjà utilisé")
    
    total_admins = db.query(Admin).count()
    if total_admins >= 6:
        raise HTTPException(status_code=403, detail="⚠️ Limite de 6 administrateurs atteinte")
    
    admin = crud.create_admin(db, signup.name, signup.phone, signup.password)
    return {"message": f"✅ Compte créé: {admin.name}", "phone": admin.phone}

@app.get("/admin/me")
async def get_admin_info(current_admin: str = Depends(get_current_admin), db: Session = Depends(get_db)):
    admin = crud.get_admin_by_phone(db, current_admin)
    return {"name": admin.name, "phone": admin.phone}

@app.get("/admin/pending")
async def get_pending_requests(db: Session = Depends(get_db), current_admin: str = Depends(get_current_admin)):
    pending = crud.get_pending_requests(db)
    return [{"device_id": p.device_id, "phone": p.phone_number, "key": p.activation_key, "months": p.months, "created": p.created.isoformat()} for p in pending]

# ✅ VOS NOUVEAUX ENDPOINTS
@app.post("/admin/validate/{device_id}")
async def validate_subscription_endpoint(device_id: str, current_admin: str = Depends(get_current_admin), db: Session = Depends(get_db)):
    print(f"🔧 Admin {current_admin} valide: {device_id}")
    admin = crud.get_admin_by_phone(db, current_admin)
    if not admin: raise HTTPException(status_code=401, detail="Admin non trouvé")
    
    success = crud.validate_subscription(db, device_id, admin.id, admin.name)
    if success:
        await manager.broadcast(json.dumps({"type": "validated", "device_id": device_id, "admin": admin.name}))
        print(f"✅ VALIDÉ + LOG: {device_id} par {admin.name}")
        return {"status": "validated", "message": "Validation réussie"}
    raise HTTPException(status_code=400, detail="Abonnement non trouvé ou déjà validé")

@app.get("/admin/clients")
async def get_all_clients(db: Session = Depends(get_db), current_admin: str = Depends(get_current_admin)):
    clients = db.query(Client).all()
    return {
        "clients": [{"id": c.id, "name": c.name or f"Client {c.phone}", "phone": c.phone, "device_id": c.device_id} for c in clients]
    }

@app.get("/admin/client/{device_id}/history")
async def get_client_history_endpoint(device_id: str, db: Session = Depends(get_db), current_admin: str = Depends(get_current_admin)):
    history = crud.get_client_history(db, device_id)
    return {
        "device_id": device_id,
        "history": [{
            "id": log.id, "client_phone": log.client_phone, "admin_name": log.admin_name,
            "months": log.months, "activation_key": log.activation_key,
            "expires_at": log.expires_at.isoformat() if log.expires_at else None,
            "validated_at": log.validated_at.isoformat()
        } for log in history]
    }

@app.get("/admin/validations")
async def get_validation_history(db: Session = Depends(get_db), current_admin: str = Depends(get_current_admin)):
    logs = crud.get_validation_history(db)
    return [{
        "id": log.id, "device_id": log.device_id, "client_phone": log.client_phone,
        "months": log.months, "key": log.activation_key, "admin": log.admin_name,
        "validated_at": log.validated_at.isoformat()
    } for log in logs]

@app.post("/admin/clear")
async def clear_all_pending(db: Session = Depends(get_db), current_admin: str = Depends(get_current_admin)):
    crud.clear_all_pending(db)
    return {"message": "Toutes les demandes supprimées"}

# STATIC + WEBSOCKET
admin_path = os.path.join(os.path.dirname(__file__), "../admin_panel")
app.mount("/static", StaticFiles(directory=admin_path), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(admin_path, "login.html"))

@app.get("/dashboard.html")
async def dashboard():
    return FileResponse(os.path.join(admin_path, "dashboard.html"))

@app.websocket("/ws/admin")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token: 
        await websocket.close(code=1008)
        return
    try:
        if jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("phone") is None:
            await websocket.close(code=1008)
            return
    except jwt.PyJWTError:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), reload=True)

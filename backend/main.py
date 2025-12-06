from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend import crud
from backend import models
from backend.database import engine, get_db
from backend.models import create_tables

import json
from typing import List
import os
from fastapi.security import HTTPBearer
import jwt
from datetime import datetime, timedelta, timezone
import bcrypt

app = FastAPI(title="_ap_bar Backend - Admin")

@app.on_event("startup")
async def startup_event():
    create_tables()  # ✅ UNE SEULE FOIS PostgreSQL

SECRET_KEY = os.getenv("SECRET_KEY", "votre_secret_super_secret_ap_bar_2025")
ALGORITHM = "HS256"
security = HTTPBearer()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for conn in self.active_connections:
            await conn.send_text(message)

manager = ConnectionManager()

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"]
)

# ✅ MODÈLES Pydantic
class SubscriptionRequest(BaseModel):
    device_id: str
    phone_number: str
    months: int

class CheckSubscriptionRequest(BaseModel):
    device_id: str

class AdminLogin(BaseModel):
    phone: str
    password: str

class AdminSignup(BaseModel):
    name: str
    phone: str
    password: str

# ✅ JWT ADMIN
def get_current_admin(token: str = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        phone = payload.get("phone")
        if phone is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        return phone
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

# ✅ API MOBILE
@app.post("/request_subscription")
async def create_subscription(request: SubscriptionRequest, db: Session = Depends(get_db)):
    existing = crud.get_subscription_by_device(db, request.device_id)
    if existing and existing.status == "pending":
        return {"activation_key": existing.activation_key, "status": "pending"}
    
    sub = crud.create_subscription(db, request.device_id, request.phone_number, request.months)
    await manager.broadcast(json.dumps({
        "type": "new_request",
        "device_id": sub.device_id,
        "phone": sub.phone_number,
        "key": sub.activation_key,
        "months": sub.months,
        "timestamp": sub.created.isoformat()
    }))
    print(f"🆕 NOUVELLE DEMANDE: {request.device_id} | Clé: {sub.activation_key}")
    return {"activation_key": sub.activation_key, "status": "pending"}

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

# ✅ ADMIN ENDPOINTS
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
    
    total_admins = db.query(models.Admin).count()
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
    return [
        {"device_id": p.device_id, "phone": p.phone_number, "key": p.activation_key, "months": p.months, "created": p.created.isoformat()}
        for p in pending
    ]

@app.get("/admin/validations")
async def get_validation_history(db: Session = Depends(get_db), current_admin: str = Depends(get_current_admin)):
    logs = crud.get_validation_history(db)
    return [
        {
            "id": log.id,
            "device_id": log.device_id,
            "client_phone": log.client_phone,
            "months": log.months,
            "key": log.activation_key,
            "admin": log.admin_name,
            "validated_at": log.validated_at.isoformat()
        }
        for log in logs
    ]

@app.post("/admin/validate/{device_id}")
async def validate_subscription(device_id: str, db: Session = Depends(get_db), current_admin: str = Depends(get_current_admin)):
    subscription = crud.get_pending_by_device(db, device_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Demande non trouvée")
    
    # 1. Valide subscription
    subscription.status = "validated"
    subscription.expires_at = datetime.now(timezone.utc) + timedelta(days=30 * subscription.months)
    
    # 2. Récupère admin
    admin = crud.get_admin_by_phone(db, current_admin)
    
    # 3. LOG validation
    crud.log_validation(
        db, device_id, subscription.phone_number, subscription.months,
        subscription.activation_key, admin.id, admin.name
    )
    
    db.commit()
    print(f"✅ VALIDÉ par {admin.name}: {device_id}")
    await manager.broadcast(json.dumps({"type": "validated", "device_id": device_id}))
    return {"message": "Abonnement validé et LOGGÉ !"}

@app.post("/admin/clear")
async def clear_all_pending(db: Session = Depends(get_db), current_admin: str = Depends(get_current_admin)):
    crud.clear_all_pending(db)
    return {"message": "Toutes les demandes supprimées"}

# ✅ FRONTEND STATIC
admin_path = os.path.join(os.path.dirname(__file__), "../admin_panel")

app.mount("/static", StaticFiles(directory=admin_path), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(admin_path, "login.html"))

@app.get("/dashboard.html")
async def dashboard():
    return FileResponse(os.path.join(admin_path, "dashboard.html"))

# ✅ WEBSOCKET UNIQUE (AVEC TOKEN VÉRIFICATION)
@app.websocket("/ws/admin")
async def websocket_endpoint(websocket: WebSocket):
    # Récupérer le token JWT envoyé en query param ?token=...
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)  # Fermeture si pas de token
        return

    # Vérifier le token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone = payload.get("phone")
        if not phone:
            await websocket.close(code=1008)
            return
    except jwt.PyJWTError:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.environ.get("PORT", 10000)), 
        reload=True
    )

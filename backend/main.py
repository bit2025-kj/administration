from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.sql import func
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPBearer
import jwt, os, json
from typing import List

from backend import crud
from backend import models
from backend.database import engine, get_db
from backend.models import create_tables, Client, ValidationLog, Subscription, Admin

# ✅ APP + MIDDLEWARE
app = FastAPI(title="_ap_bar Backend - Admin")

@app.on_event("startup")
async def startup():
    create_tables()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ✅ JWT + WEBSOCKET
SECRET_KEY = os.getenv("SECRET_KEY", "votre_secret_super_secret_ap_bar_2025")
ALGORITHM = "HS256"
security = HTTPBearer()

class ConnectionManager:
    def __init__(self): self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket): await websocket.accept(); self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket): self.active_connections.remove(websocket)
    async def broadcast(self, message: str): for conn in self.active_connections: await conn.send_text(message)

manager = ConnectionManager()

def get_current_admin(token: str = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        phone = payload.get("phone")
        if phone is None: raise HTTPException(status_code=401, detail="Token invalide")
        return phone
    except jwt.PyJWTError: raise HTTPException(status_code=401, detail="Token invalide")

# ✅ MODÈLES + CLIENT_NAME
class SubscriptionRequest(BaseModel):
    device_id: str
    client_name: str          # ✅ NOUVEAU
    phone_number: str
    months: int

class CheckSubscriptionRequest(BaseModel):
    device_id: str

# ✅ MOBILE API
@app.post("/request_subscription")
async def create_subscription(request: SubscriptionRequest, db: Session = Depends(get_db)):
    existing = crud.get_subscription_by_device(db, request.device_id)
    if existing and existing.status == "pending":
        return {"activation_key": existing.activation_key, "status": "pending"}
    
    sub = crud.create_subscription(db, request.device_id, request.phone_number, request.months)
    await manager.broadcast(json.dumps({
        "type": "new_request",
        "device_id": sub.device_id,
        "client_name": request.client_name,  # ✅ NOM !
        "phone": sub.phone_number,
        "key": sub.activation_key,
        "months": sub.months,
        "timestamp": sub.created.isoformat()
    }))
    print(f"🆕 {request.client_name}: {request.device_id} | Clé: {sub.activation_key}")
    return {"activation_key": sub.activation_key, "status": "pending"}

@app.post("/check_subscription")
async def check_subscription(request: CheckSubscriptionRequest, db: Session = Depends(get_db)):
    sub = crud.get_subscription_by_device(db, request.device_id)
    if not sub: return {"error": "Device non trouvé"}
    return {
        "activation_key": sub.activation_key,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "status": sub.status
    }

# ✅ ADMIN API (votre code existant)
@app.post("/admin/login")
async def admin_login(login: AdminLogin, db: Session = Depends(get_db)):
    # ... votre code login existant

# ✅ VOS NOUVEAUX ENDPOINTS (CORRIGÉS)
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

# ✅ STATIC + WEBSOCKET (votre code existant)
admin_path = os.path.join(os.path.dirname(__file__), "../admin_panel")
app.mount("/static", StaticFiles(directory=admin_path), name="static")
@app.get("/") async def root(): return FileResponse(os.path.join(admin_path, "login.html"))

@app.websocket("/ws/admin")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token or jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("phone") is None:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try: while True: await websocket.receive_text()
    except WebSocketDisconnect: manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), reload=True)

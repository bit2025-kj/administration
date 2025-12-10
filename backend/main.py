from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.sql import func
from datetime import timedelta

# ✅ IMPORTS CORRIGÉS
from backend import crud
from backend import models
from backend.database import engine, get_db
from backend.models import create_tables, Client, ValidationLog, Subscription, Admin

# ... (votre code existant jusqu'aux modèles Pydantic OK)

# ✅ ENDPOINT VALIDATE CORRIGÉ
@app.post("/admin/validate/{device_id}")
async def validate_subscription_endpoint(
    device_id: str, 
    current_admin: str = Depends(get_current_admin),  # ✅ JWT
    db: Session = Depends(get_db)
):
    """Validation complète : Client + Subscription + Log historique"""
    print(f"🔧 Admin {current_admin} valide: {device_id}")
    
    # ✅ Utilise CRUD corrigé
    admin = crud.get_admin_by_phone(db, current_admin)
    if not admin:
        raise HTTPException(status_code=401, detail="Admin non trouvé")
    
    success = crud.validate_subscription(db, device_id, admin.id, admin.name)
    
    if success:
        # ✅ Broadcast à TOUS admins
        await manager.broadcast(json.dumps({
            "type": "validated",
            "device_id": device_id,
            "admin": admin.name,
            "timestamp": func.now()
        }))
        print(f"✅ VALIDÉ + LOG: {device_id} par {admin.name}")
        return {"status": "validated", "message": "Validation réussie"}
    raise HTTPException(status_code=400, detail="Abonnement non trouvé ou déjà validé")

# ✅ NOUVEAU : Liste TOUS clients
@app.get("/admin/clients")
async def get_all_clients(db: Session = Depends(get_db), current_admin: str = Depends(get_current_admin)):
    """Liste tous clients + device_id"""
    clients = db.query(Client).all()
    return {
        "clients": [
            {
                "id": c.id,
                "name": c.name or f"Client {c.phone}",
                "phone": c.phone,
                "device_id": c.device_id
            }
            for c in clients
        ]
    }

# ✅ NOUVEAU : Historique PAR CLIENT/DEVICE
@app.get("/admin/client/{device_id}/history")
async def get_client_history_endpoint(
    device_id: str, 
    db: Session = Depends(get_db), 
    current_admin: str = Depends(get_current_admin)
):
    """Historique complet d'un client par device_id"""
    history = crud.get_client_history(db, device_id)
    return {
        "device_id": device_id,
        "history": [
            {
                "id": log.id,
                "client_phone": log.client_phone,
                "admin_name": log.admin_name,
                "months": log.months,
                "activation_key": log.activation_key,
                "expires_at": log.expires_at.isoformat() if log.expires_at else None,
                "validated_at": log.validated_at.isoformat()
            }
            for log in history
        ]
    }

# ✅ CORRIGEZ votre endpoint /admin/validations existant
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

# ✅ SUPPRIMEZ l'ancien endpoint cassé /admin/client/{client_id}/history
# Gardez TOUT le reste (WebSocket, static, etc.) IDENTIQUE ✅

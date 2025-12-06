#!/bin/bash

# Mise à jour DB si alembic existe
if [ -d "alembic" ]; then
    alembic upgrade head
fi

# Lancer FastAPI
exec uvicorn backend.main:app --host 0.0.0.0 --port $PORT



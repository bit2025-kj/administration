#!/bin/bash

# Mise à jour DB si alembic existe
if [ -d "alembic" ]; then
    alembic upgrade head
fi

# Lancer FastAPI
exec uvicorn app.main:app --host 0.0.0.0 --port 10000


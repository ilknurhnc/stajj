import json
import os
from fastapi import FastAPI, HTTPException

app = FastAPI()

SCHEMA_DIR = os.getenv("SCHEMA_DIR", "/data/schemas")


@app.get("/{app_name}")
def get_schema(app_name: str):

    path = os.path.join(SCHEMA_DIR, f"{app_name}.schema.json")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Schema not found")

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

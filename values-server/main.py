import json
import os
from fastapi import FastAPI, HTTPException

app = FastAPI()
VALUES_DIR = os.getenv("VALUES_DIR", "/data/values")

@app.get("/{app_name}")
def get_values(app_name: str):
    path = os.path.join(VALUES_DIR, f"{app_name}.value.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Values not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

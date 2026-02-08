import os
import json
import re
import logging
from typing import Any, Dict

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from jsonschema import validate
from jsonschema.exceptions import ValidationError

SCHEMA_URL = os.getenv("SCHEMA_URL", "http://schema-server:5001")
VALUES_URL = os.getenv("VALUES_URL", "http://values-server:5002")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:latest")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30"))

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot-server")

class MessageIn(BaseModel):
    input: str

def deep_copy(obj: Any) -> Any:
    return json.loads(json.dumps(obj))

def set_by_dot_path(obj: Dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    cur = obj
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value

def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0},
    }
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
    r.raise_for_status()
    txt = (r.json().get("response") or "").strip()
    return txt

def llm_get_patch(user_input: str) -> Dict[str, Any]:
    prompt = (
        "You are a config assistant.\n"
        "Return JSON only. No markdown. No explanation.\n"
        "Choose app from: chat, matchmaking, tournament.\n"
        "Return fields: app, path, value.\n"
        "path must be a dot-separated path inside the values JSON.\n"
        "Use integer for replicas.\n"
        "Examples:\n"
        '{"app":"chat","path":"workloads.deployments.chat.replicas","value":3}\n'
        '{"app":"tournament","path":"workloads.statefulsets.tournament.replicas","value":4}\n'
        "\n"
        f"User input: {user_input}\n"
        "JSON:"
    )

    raw = call_ollama(prompt)

    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not m:
        raise ValueError(f"LLM did not return JSON. Raw: {raw[:200]}")
    patch = json.loads(m.group(0))

    if not isinstance(patch, dict):
        raise ValueError("Patch is not an object")
    if "app" not in patch or "path" not in patch or "value" not in patch:
        raise ValueError("Patch missing fields (app, path, value)")
    return patch


def fetch_schema_and_values(app_name: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    schema_resp = requests.get(f"{SCHEMA_URL}/{app_name}", timeout=HTTP_TIMEOUT)
    values_resp = requests.get(f"{VALUES_URL}/{app_name}", timeout=HTTP_TIMEOUT)

    schema_resp.raise_for_status()
    values_resp.raise_for_status()

    return schema_resp.json(), values_resp.json()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug/{app_name}")
def debug(app_name: str):
    if app_name not in {"chat", "matchmaking", "tournament"}:
        raise HTTPException(status_code=400, detail="Unknown app_name")
    schema, values = fetch_schema_and_values(app_name)
    return {"app": app_name, "schema": schema, "values": values}

@app.post("/message")
def message(body: MessageIn):
    user_input = body.input.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="input is empty")

    logger.info("Received input: %s", user_input)

    try:
        patch = llm_get_patch(user_input)
        app_name = patch["app"]
        path = patch["path"]
        value = patch["value"]

        if app_name not in {"chat", "matchmaking", "tournament"}:
            raise ValueError("invalid app")
        if not isinstance(path, str) or "." not in path:
            raise ValueError("invalid path")
    except Exception as e:
        logger.exception("Patch generation failed")
        raise HTTPException(status_code=500, detail=f"Patch generation failed: {e}")

    logger.info("Patch: app=%s path=%s value=%s", app_name, path, value)

    try:
        schema, values = fetch_schema_and_values(app_name)
    except Exception as e:
        logger.exception("Fetch schema/values failed")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {e}")

    try:
        new_values = deep_copy(values)

        if path.endswith(".replicas"):
            try:
                value = int(value)
            except Exception:
                raise ValueError("replicas must be an integer")
        set_by_dot_path(new_values, path, value)
    except Exception as e:
        logger.exception("Patch apply failed")
        raise HTTPException(status_code=500, detail=f"Patch apply failed: {e}")

    try:
        validate(instance=new_values, schema=schema)
    except ValidationError as e:
        logger.warning("Validation failed: %s", e.message)
        raise HTTPException(status_code=400, detail=f"Validation failed: {e.message}")
    except Exception as e:
        logger.exception("Validation error")
        raise HTTPException(status_code=500, detail=f"Validation error: {e}")

    logger.info("Validation OK, returning updated values for %s", app_name)
    return new_values

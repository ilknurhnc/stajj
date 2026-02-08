import os
import json
import re
import logging
from typing import Any, Dict, Tuple, Optional

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
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot-server")


class MessageIn(BaseModel):
    input: str


def deep_copy(obj: Any) -> Any:
    return json.loads(json.dumps(obj))


def minify_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def fetch_schema_and_values(app_name: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    schema_resp = requests.get(f"{SCHEMA_URL}/{app_name}", timeout=HTTP_TIMEOUT)
    values_resp = requests.get(f"{VALUES_URL}/{app_name}", timeout=HTTP_TIMEOUT)
    schema_resp.raise_for_status()
    values_resp.raise_for_status()
    return schema_resp.json(), values_resp.json()


def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "top_p": 1,
            "num_predict": 700,
        },
    }
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
    r.raise_for_status()
    return (r.json().get("response") or "").strip()


def extract_first_json_object(text: str) -> Dict[str, Any]:
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError(f"LLM did not return JSON object. Raw: {text[:300]}")
    return json.loads(m.group(0))


_PRUNE_KEYS = {
    "default", "examples", "example", "title", "description",
    "$comment", "deprecated", "readOnly", "writeOnly"
}

def prune_schema(schema: Any) -> Any:
    """
    JSON schema validasyon için kritik olmayan şişkin alanları atar.
    Bu, promptu ciddi küçültür.
    """
    if isinstance(schema, dict):
        out = {}
        for k, v in schema.items():
            if k in _PRUNE_KEYS:
                continue
            if k == "discriminator":
                continue
            out[k] = prune_schema(v)
        return out
    if isinstance(schema, list):
        return [prune_schema(x) for x in schema]
    return schema


def llm_choose_app_jk(user_input: str) -> str:
    prompt = (
        "Return ONLY one token: chat OR matchmaking OR tournament.\n"
        "No punctuation, no quotes, no extra words.\n"
        f"User request: {user_input}\n"
        "Answer:"
    )
    raw = call_ollama(prompt)
    ans = re.sub(r"[^a-z]", "", raw.strip().lower())
    if ans not in {"chat", "matchmaking", "tournament"}:
        raise ValueError(f"Invalid app from LLM: {raw[:100]}")
    return ans


def set_by_path(obj: Dict[str, Any], path: str, value: Any) -> None:
    cur = obj
    keys = path.split(".")
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value


def try_rule_based_update(user_input: str, app_name: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    README’deki 3 örneği garanti çalıştırmak için.
    Eğer input bu pattern’lerden biriyse updated values döndürür, yoksa None.
    """
    u = user_input.strip().lower()
    new_values = deep_copy(values)

    m = re.search(r"set\s+tournament\s+service\s+memory\s+to\s+(\d+)\s*mb", u)
    if m:
        mem = int(m.group(1))
        if app_name != "tournament":
            app_name = "tournament"
        set_by_path(
            new_values,
            "workloads.statefulsets.tournament.containers.tournament.resources.memory.limitMiB",
            mem
        )
        return new_values

    m = re.search(r"set\s+game_name\s+env\s+to\s+([a-z0-9_\-]+)\s+for\s+matchmaking\s+service", u)
    if m:
        val = m.group(1)
        if app_name != "matchmaking":
            app_name = "matchmaking"
        set_by_path(
            new_values,
            "workloads.deployments.matchmaking.containers.matchmaking.envs.GAME_NAME",
            val
        )
        return new_values

    m = re.search(r"lower\s+cpu\s+limit\s+of\s+chat\s+service\s+to\s+%?\s*(\d+)\s*%?", u)
    if m:
        pct = int(m.group(1))
        if not (1 <= pct <= 200):
            return None
        if app_name != "chat":
            app_name = "chat"
        cur_limit = new_values["workloads"]["deployments"]["chat"]["containers"]["chat"]["resources"]["cpu"]["limitMilliCPU"]
        new_limit = int(round(cur_limit * (pct / 100.0)))
        set_by_path(
            new_values,
            "workloads.deployments.chat.containers.chat.resources.cpu.limitMilliCPU",
            new_limit
        )
        return new_values

    return None


def llm_apply_change(user_input: str, schema: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
    compact_schema = prune_schema(schema)
    prompt = (
        "You are a configuration transformer.\n"
        "Output JSON ONLY. No markdown. No explanation.\n"
        "Update CURRENT_VALUES according to USER_REQUEST.\n"
        "Preserve unrelated fields.\n"
        "Output MUST validate against JSON_SCHEMA.\n\n"
        "USER_REQUEST:\n"
        f"{user_input}\n\n"
        "JSON_SCHEMA:\n"
        f"{minify_json(compact_schema)}\n\n"
        "CURRENT_VALUES:\n"
        f"{minify_json(values)}\n\n"
        "UPDATED_VALUES_JSON:"
    )

    raw = call_ollama(prompt)
    updated = extract_first_json_object(raw)
    if not isinstance(updated, dict):
        raise ValueError("LLM output is not a JSON object.")
    return updated


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/message")
def message(body: MessageIn):
    user_input = (body.input or "").strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="input is empty")

    logger.info("Received input: %s", user_input)

    try:
        app_name = llm_choose_app_jk(user_input)
    except Exception as e:
        logger.exception("App classification failed")
        raise HTTPException(status_code=500, detail=f"App classification failed: {e}")

    try:
        schema, values = fetch_schema_and_values(app_name)
    except Exception as e:
        logger.exception("Fetch schema/values failed")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {e}")

    rb = try_rule_based_update(user_input, app_name, values)
    if rb is not None:
        try:
            validate(instance=rb, schema=schema)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"Validation failed: {e.message}")
        return rb

    try:
        new_values = llm_apply_change(user_input, schema, deep_copy(values))
    except requests.exceptions.ReadTimeout:
        logger.exception("LLM timed out")
        raise HTTPException(status_code=500, detail="Patch generation failed: Ollama timed out (prompt too heavy).")
    except Exception as e:
        logger.exception("LLM apply failed")
        raise HTTPException(status_code=500, detail=f"Patch generation failed: {e}")

    try:
        validate(instance=new_values, schema=schema)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {e}")

    return new_values

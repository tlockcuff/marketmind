from typing import Optional
from fastapi import APIRouter, HTTPException
from api.data_provider import get_config
from config import settings

router = APIRouter()


@router.get("/api/config")
async def config():
    return get_config()


@router.post("/api/config")
async def update_config(body: dict):
    errors = {}
    validated = {}
    for key, value in body.items():
        key = key.lower()
        if key not in settings.EDITABLE_SETTINGS:
            errors[key] = f"unknown setting: {key}"
            continue
        ok, msg = settings.validate_setting(key, value)
        if not ok:
            errors[key] = msg
        else:
            # Cast to correct type
            meta = settings.EDITABLE_SETTINGS[key]
            if meta["type"] == "int":
                value = int(value)
            elif meta["type"] == "float":
                value = float(value)
            validated[key] = value
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    # Cross-validate related settings
    cross_errors = settings.validate_config_cross(validated)
    if cross_errors:
        raise HTTPException(status_code=400, detail={"_cross_validation": cross_errors})

    settings.set_config_overrides(validated)
    return {"updated": list(validated.keys())}


@router.delete("/api/config")
async def reset_config(body: Optional[dict] = None):
    if body and "keys" in body:
        settings.clear_config_overrides(body["keys"])
        return {"cleared": body["keys"]}
    settings.clear_config_overrides()
    return {"cleared": "all"}

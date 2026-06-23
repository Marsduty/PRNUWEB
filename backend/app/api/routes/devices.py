import secrets
import string

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.device import Device

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceCreate(BaseModel):
    brand: str
    model: str
    mac_address: str | None = None
    notes: str | None = None


class DeviceUpdate(BaseModel):
    brand: str | None = None
    model: str | None = None
    mac_address: str | None = None
    notes: str | None = None


def _random_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_device_name(brand: str, model: str) -> str:
    safe_brand = brand.strip().replace(" ", "")
    safe_model = model.strip().replace(" ", "")
    return f"{safe_brand}-{safe_model}-{_random_code()}"


def apply_device_updates(device: Device, payload: DeviceUpdate) -> None:
    brand_or_model_changed = False
    for field in ["brand", "model", "mac_address", "notes"]:
        value = getattr(payload, field)
        if value is not None:
            if field in {"brand", "model"} and getattr(device, field) != value:
                brand_or_model_changed = True
            setattr(device, field, value)
    if brand_or_model_changed and device.brand and device.model:
        device.name = generate_device_name(device.brand, device.model)


def device_to_dict(device: Device):
    return {
        "id": device.id,
        "name": device.name,
        "brand": device.brand,
        "model": device.model,
        "mac_address": device.mac_address,
        "notes": device.notes,
        "created_at": device.created_at,
    }


@router.get("")
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).order_by(Device.created_at.desc()).all()
    return [device_to_dict(item) for item in devices]


@router.post("")
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    device = Device(
        name=generate_device_name(payload.brand, payload.model),
        brand=payload.brand,
        model=payload.model,
        mac_address=payload.mac_address,
        notes=payload.notes,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device_to_dict(device)


@router.patch("/{device_id}")
def update_device(device_id: int, payload: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    apply_device_updates(device, payload)
    db.commit()
    db.refresh(device)
    return device_to_dict(device)

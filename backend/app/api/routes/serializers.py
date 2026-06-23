from app.models.comparison_result import ComparisonResult
from app.models.device import Device
from app.models.fingerprint import Fingerprint


def device_to_summary(device: Device | None):
    if device is None:
        return None
    return {
        "id": device.id,
        "name": device.name,
        "brand": device.brand,
        "model": device.model,
        "mac_address": device.mac_address,
    }


def fingerprint_to_summary(fingerprint: Fingerprint | None):
    if fingerprint is None:
        return None
    return {
        "id": fingerprint.id,
        "image_count": fingerprint.image_count,
        "height": fingerprint.height,
        "width": fingerprint.width,
        "created_at": fingerprint.created_at,
    }


def comparison_decision(row: ComparisonResult) -> str:
    if row.comparison_type != "database_comparison":
        return row.decision
    if not row.is_hit:
        return "库中未检索到匹配设备"
    device_name = row.candidate_device.name if row.candidate_device is not None else "未知设备"
    return f"倾向认定设备指纹：{device_name} 与待检图像同源"


def _pce_sort_value(row: ComparisonResult) -> float:
    return row.pce if row.pce is not None else float("-inf")


def visible_comparison_rows(rows: list[ComparisonResult]) -> list[ComparisonResult]:
    if not rows:
        return []
    if rows[0].comparison_type != "database_comparison":
        return rows
    hit_rows = [row for row in rows if row.is_hit]
    if hit_rows:
        return hit_rows
    return [max(rows, key=_pce_sort_value)]

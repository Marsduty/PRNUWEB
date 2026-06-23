from pathlib import Path

import numpy as np

from app.services.image_preprocess import load_rgb_square
from prnu_core import get_fingerprint, ncc_score, pce_score, rank_references


DEFAULT_ENHANCEMENT_CONFIG = (1, 0, 0, 0, 0)


def build_device_fingerprint(
    image_bytes_list: list[bytes],
    output_size: int = 1024,
    enhancement_config=DEFAULT_ENHANCEMENT_CONFIG,
) -> np.ndarray:
    images = [load_rgb_square(image_bytes, output_size=output_size) for image_bytes in image_bytes_list]
    return get_fingerprint(images, enh_list=enhancement_config)


def build_single_image_fingerprint(
    image_bytes: bytes,
    output_size: int = 1024,
    enhancement_config=DEFAULT_ENHANCEMENT_CONFIG,
) -> np.ndarray:
    image = load_rgb_square(image_bytes, output_size=output_size)
    return get_fingerprint([image], enh_list=enhancement_config)


def load_fingerprint_array(path: str | Path) -> np.ndarray:
    return np.load(path)


def compare_with_database(query_fingerprint: np.ndarray, database_fingerprints: dict[str, np.ndarray], threshold: float = 60):
    candidates = rank_references(query_fingerprint, database_fingerprints, top_k=max(len(database_fingerprints), 1), include_pce=True)
    return decide_database_matches(candidates, threshold=threshold)


def compare_external_images(fingerprint_a: np.ndarray, fingerprint_b: np.ndarray, threshold: float = 60):
    ncc = ncc_score(fingerprint_a, fingerprint_b)
    result = pce_score(fingerprint_a, fingerprint_b)
    decision = decide_external_match(result["pce"], threshold=threshold)
    return {**result, "ncc": ncc, **decision}


def decide_database_matches(candidates: list[dict], threshold: float = 60):
    sorted_candidates = sorted(candidates, key=lambda item: float(item.get("pce", 0)), reverse=True)
    rows = []
    for index, candidate in enumerate(sorted_candidates, start=1):
        pce = float(candidate.get("pce", 0))
        is_hit = pce > float(threshold)
        name = str(candidate.get("name", candidate.get("candidate", "未知设备")))
        decision = f"倾向认定设备指纹：{name} 与待检图像同源" if is_hit else "库中未检索到匹配设备"
        rows.append({**candidate, "rank": index, "pce": pce, "is_hit": is_hit, "decision": decision})

    hits = [row for row in rows if row["is_hit"]]
    if not hits:
        return {"decision": "库中未检索到匹配设备", "hits": [], "candidates": rows}

    best = hits[0]
    return {
        "decision": best["decision"],
        "hits": hits,
        "candidates": rows,
    }


def decide_external_match(pce: float, threshold: float = 60):
    is_hit = float(pce) > float(threshold)
    decision = "倾向认定图像 A 和图像 B 同源" if is_hit else "倾向认定图像 A 和图像 B 不同源"
    return {"is_hit": is_hit, "decision": decision, "threshold": float(threshold)}

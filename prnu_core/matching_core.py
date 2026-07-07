import math

import numpy as np


def _pad_to_match(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """将两个 2D 数组 padding 到二者尺寸的最大值，右侧和下方补零。"""
    if a.shape == b.shape:
        return a, b
    h = max(a.shape[0], b.shape[0])
    w = max(a.shape[1], b.shape[1])
    result = []
    for arr in (a, b):
        if arr.shape == (h, w):
            result.append(arr)
            continue
        padded = np.zeros((h, w), dtype=arr.dtype)
        padded[: arr.shape[0], : arr.shape[1]] = arr
        result.append(padded)
    return result[0], result[1]


def normalize_fingerprint(fingerprint):
    """Return a zero-mean, unit-norm vector for a 2D PRNU fingerprint."""
    arr = np.asarray(fingerprint, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError(f"Expected a 2D PRNU fingerprint, got shape={arr.shape}")

    vec = arr.reshape(-1).astype(np.float32, copy=True)
    vec -= float(vec.mean())
    norm = float(np.linalg.norm(vec))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError(f"Invalid PRNU norm={norm}")
    vec /= norm
    return np.ascontiguousarray(vec, dtype=np.float32), tuple(int(v) for v in arr.shape)


def ncc_score(query_fingerprint, reference_fingerprint):
    """Compute normalized cross-correlation between two PRNU fingerprints."""
    query_fingerprint, reference_fingerprint = _pad_to_match(
        np.asarray(query_fingerprint, dtype=np.float32),
        np.asarray(reference_fingerprint, dtype=np.float32),
    )
    query_vec, _ = normalize_fingerprint(query_fingerprint)
    reference_vec, _ = normalize_fingerprint(reference_fingerprint)
    return float(reference_vec @ query_vec)


def pce_from_corr(corr, exclusion_radius=5):
    """Compute PCE, peak value, and peak position from a circular correlation plane."""
    corr = np.asarray(corr, dtype=np.float32)
    if corr.ndim != 2:
        raise ValueError(f"Expected a 2D correlation plane, got shape={corr.shape}")

    peak_flat = int(np.argmax(corr))
    peak_pos = [int(value) for value in np.unravel_index(peak_flat, corr.shape)]
    peak = float(corr[tuple(peak_pos)])

    rows, cols = corr.shape
    excluded = {
        ((peak_pos[0] + dr) % rows, (peak_pos[1] + dc) % cols)
        for dr in range(-int(exclusion_radius), int(exclusion_radius) + 1)
        for dc in range(-int(exclusion_radius), int(exclusion_radius) + 1)
    }

    side_values = [
        float(corr[row, col])
        for row in range(rows)
        for col in range(cols)
        if (row, col) not in excluded
    ]
    side_mean = float(np.mean(np.square(side_values, dtype=np.float64))) if side_values else 1e-30
    pce = math.copysign((peak * peak) / max(side_mean, 1e-30), peak)
    return float(pce), peak, peak_pos


def pce_score(query_fingerprint, reference_fingerprint, exclusion_radius=5):
    """Compute PCE between two PRNU fingerprints. 自动补零对齐尺寸。"""
    query_fingerprint, reference_fingerprint = _pad_to_match(
        np.asarray(query_fingerprint, dtype=np.float32),
        np.asarray(reference_fingerprint, dtype=np.float32),
    )
    query_vec, query_shape = normalize_fingerprint(query_fingerprint)
    reference_vec, reference_shape = normalize_fingerprint(reference_fingerprint)

    query_fft = np.fft.fft2(query_vec.reshape(query_shape))
    reference_fft = np.fft.fft2(reference_vec.reshape(reference_shape))
    corr = np.fft.ifft2(query_fft * np.conj(reference_fft)).real.astype(np.float32, copy=False)
    pce, peak, peak_pos = pce_from_corr(corr, exclusion_radius)
    return {"pce": pce, "peak": peak, "peak_pos": peak_pos}


def rank_references(query_fingerprint, references, top_k=5, include_pce=False):
    """Rank reference PRNU fingerprints by PCE (deprecated: always computes PCE directly)."""
    top_k = max(int(top_k), 1)
    rows = []
    for name, reference in references.items():
        result = pce_score(query_fingerprint, reference)
        result["name"] = name
        rows.append(result)
    rows.sort(key=lambda item: item["pce"], reverse=True)
    return rows[:top_k]

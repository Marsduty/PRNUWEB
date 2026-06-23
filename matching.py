"""NCC/PCE matching for extracted PRNU fingerprints.

当前项目重新收口后只保留 PRNU 基础链路，因此这里提供一个轻量的
matching 入口：默认每台设备抽 1 个单图 query 做 NCC/PCE；如果需要
完整单图评估，再显式启用 all query。
"""

from __future__ import annotations

import csv
import json
import math
import time
from pathlib import Path

import numpy as np

try:
    from .config import PRNU_MATCHING_DIR, PRNU_OUTPUT_ROOT, PROJECT_ROOT, QUERY_SET_DIR, REFERENCE_DB_DIR
    from .main import collect_image_paths, query_output_stem
    from .matching_core import normalize_fingerprint, pce_from_corr
except ImportError:
    try:
        from config import PRNU_MATCHING_DIR, PRNU_OUTPUT_ROOT, PROJECT_ROOT, QUERY_SET_DIR, REFERENCE_DB_DIR
        from main import collect_image_paths, query_output_stem
    except ImportError:
        PRNU_MATCHING_DIR = None
        PRNU_OUTPUT_ROOT = None
        PROJECT_ROOT = None
        QUERY_SET_DIR = None
        REFERENCE_DB_DIR = None
        collect_image_paths = None
        query_output_stem = None
    from matching_core import normalize_fingerprint, pce_from_corr


def _require_project_config() -> None:
    if any(value is None for value in [PRNU_MATCHING_DIR, PRNU_OUTPUT_ROOT, PROJECT_ROOT, QUERY_SET_DIR, REFERENCE_DB_DIR]):
        raise RuntimeError("Project PRNU config is not available. Use matching_core for direct API calls.")
    if collect_image_paths is None or query_output_stem is None:
        raise RuntimeError("Project image path helpers are not available. Use matching_core for direct API calls.")


def _dirs_for_size(size: int) -> tuple[Path, Path]:
    """返回指定尺寸的 reference/query PRNU 目录。"""
    _require_project_config()
    size = int(size)
    if size == 1024:
        return Path(REFERENCE_DB_DIR), Path(QUERY_SET_DIR)
    root = Path(PRNU_OUTPUT_ROOT) / f"size_{size}"
    return root / "Reference_DB", root / "Query_Set"


def _query_dataset_dir_for_size(size: int) -> Path:
    """返回当前尺寸对应的 query 裁剪数据集目录。"""
    _require_project_config()
    if int(size) == 1024:
        return Path(PROJECT_ROOT) / "Dataset_query_cropped"
    return Path(PROJECT_ROOT) / f"Dataset_query_cropped_{int(size)}"


def _active_query_stems(size: int) -> set[str]:
    """根据当前 query 裁剪数据集生成有效输出 stem，用来忽略旧孤儿输出。"""
    dataset_dir = _query_dataset_dir_for_size(size)
    if not dataset_dir.is_dir():
        return set()
    stems = set()
    for camera_dir in sorted(path for path in dataset_dir.iterdir() if path.is_dir()):
        for image_path in collect_image_paths(str(camera_dir)):
            stems.add(query_output_stem(camera_dir.name, image_path, str(camera_dir)))
    return stems


def _select_query_paths(query_paths: list[Path], policy: str) -> list[Path]:
    """按评估策略选择 query 指纹。

    one-per-device 用于快速 sanity check：每台设备取排序后的第一个单图
    query，避免 1.2 万张 query 的全量 NCC/PCE 过重。
    """
    if policy == "all":
        return query_paths
    if policy != "one-per-device":
        raise ValueError(f"Unknown query policy: {policy}")

    selected = {}
    for path in query_paths:
        device = _device_from_query_stem(path.stem)
        selected.setdefault(device, path)
    return [selected[device] for device in sorted(selected)]


def _device_from_query_stem(stem: str) -> str:
    """单图 query 的 stem 形如 <device>__<relative-image-stem>。"""
    return stem.split("__", 1)[0]


def _load_normalized_vector(path: Path) -> tuple[np.ndarray, tuple[int, int]]:
    """加载 PRNU，并转成零均值、单位范数的 float32 向量。"""
    arr = np.load(path, mmap_mode="r")
    try:
        return normalize_fingerprint(arr)
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc


def _pce_from_corr(corr: np.ndarray, exclusion_radius: int = 5) -> tuple[float, float, list[int]]:
    """从循环互相关平面计算 PCE。

    PCE 使用峰值能量除以旁瓣均方能量。为避免每次分配巨大 mask，这里用
    总能量减去峰值邻域能量来估计旁瓣能量。
    """
    return pce_from_corr(corr, exclusion_radius)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_current_ref_query_paths(
    size: int,
    query_policy: str = "one-per-device",
    limit_queries: int | None = None,
) -> tuple[list[Path], list[Path]]:
    """读取当前有效 reference/query PRNU 路径。

    query 默认按设备抽 1 个单图指纹。这样每次运行都是 103 个 query
    对 103 个 reference，而不是 1.2 万张单图全量展开。
    """
    ref_dir, query_dir = _dirs_for_size(size)
    ref_paths = sorted(ref_dir.glob("*.npy"))
    query_paths = sorted(query_dir.glob("*.npy"))
    active_query_stems = _active_query_stems(size)
    if active_query_stems:
        before_count = len(query_paths)
        query_paths = [path for path in query_paths if path.stem in active_query_stems]
        ignored_count = before_count - len(query_paths)
        if ignored_count:
            print(f"[INFO] Ignored {ignored_count} stale query PRNU files not present in current Dataset_query_cropped.")

    query_paths = _select_query_paths(query_paths, query_policy)
    if limit_queries is not None:
        query_paths = query_paths[: int(limit_queries)]

    if not ref_paths:
        raise FileNotFoundError(f"Reference PRNU not found: {ref_dir}")
    if not query_paths:
        raise FileNotFoundError(f"Query PRNU not found: {query_dir}")
    return ref_paths, query_paths


def _threshold_for_target_fpr(negative_scores: np.ndarray, target_fpr: float) -> tuple[float, int]:
    """返回使经验 FPR 不超过目标值的阈值。

    当前每设备 1 个 query 时，负样本数量约为 1 万，无法直接解析到 1e-6。
    因此 target_fpr=1e-6 会得到一个高于最大负样本分数的阈值，即经验
    FPR 为 0。这比在测试集上强行插值更保守。
    """
    negative_scores = np.asarray(negative_scores, dtype=np.float64)
    if negative_scores.size == 0:
        return float("inf"), 0

    allowed_fp = int(math.floor(float(target_fpr) * negative_scores.size))
    sorted_desc = np.sort(negative_scores)[::-1]
    if allowed_fp <= 0:
        return float(np.nextafter(sorted_desc[0], np.inf)), allowed_fp
    if allowed_fp >= negative_scores.size:
        return float(sorted_desc[-1]), allowed_fp
    return float(np.nextafter(sorted_desc[allowed_fp], np.inf)), allowed_fp


def _verification_metrics(score_matrix: np.ndarray, ref_names: list[str], query_names: list[str], threshold: float) -> dict:
    """按阈值统计 TPR/FPR，分数越大越匹配。"""
    pos_scores = []
    neg_scores = []
    for qi, query_name in enumerate(query_names):
        query_device = _device_from_query_stem(query_name)
        for ri, ref_name in enumerate(ref_names):
            score = float(score_matrix[qi, ri])
            if ref_name == query_device:
                pos_scores.append(score)
            else:
                neg_scores.append(score)

    pos_scores_np = np.asarray(pos_scores, dtype=np.float64)
    neg_scores_np = np.asarray(neg_scores, dtype=np.float64)
    tp = int(np.count_nonzero(pos_scores_np >= threshold))
    fp = int(np.count_nonzero(neg_scores_np >= threshold))
    pos_count = int(pos_scores_np.size)
    neg_count = int(neg_scores_np.size)
    return {
        "threshold": float(threshold),
        "tp": tp,
        "fp": fp,
        "fn": int(pos_count - tp),
        "tn": int(neg_count - fp),
        "positive_count": pos_count,
        "negative_count": neg_count,
        "tpr": tp / pos_count if pos_count else 0.0,
        "fpr": fp / neg_count if neg_count else 0.0,
    }


def _top1_metrics(score_matrix: np.ndarray, ref_names: list[str], query_names: list[str]) -> dict:
    """统计 closed-set Top-1。"""
    rows = []
    correct = 0
    for qi, query_name in enumerate(query_names):
        best_idx = int(np.argmax(score_matrix[qi]))
        query_device = _device_from_query_stem(query_name)
        best_ref = ref_names[best_idx]
        is_match = best_ref == query_device
        correct += int(is_match)
        rows.append(
            {
                "query": query_name,
                "query_device": query_device,
                "reference": best_ref,
                "is_match": int(is_match),
                "score": float(score_matrix[qi, best_idx]),
            }
        )
    return {"accuracy": correct / len(query_names), "correct": correct, "total": len(query_names), "rows": rows}


def _write_top1_csv(path: Path, rows: list[dict], score_name: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "query_device", "reference", "is_match", score_name])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "query": row["query"],
                    "query_device": row["query_device"],
                    "reference": row["reference"],
                    "is_match": row["is_match"],
                    score_name: f"{row['score']:.10f}",
                }
            )


def _write_pair_csv(path: Path, score_matrix: np.ndarray, ref_names: list[str], query_names: list[str], score_name: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["query", "query_device", "reference", "is_match", score_name])
        for qi, query_name in enumerate(query_names):
            query_device = _device_from_query_stem(query_name)
            for ri, ref_name in enumerate(ref_names):
                writer.writerow(
                    [
                        query_name,
                        query_device,
                        ref_name,
                        int(ref_name == query_device),
                        f"{float(score_matrix[qi, ri]):.10f}",
                    ]
                )


def _write_summary(out_dir: Path, name: str, summary: dict) -> None:
    (out_dir / f"{name}_Summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# {name} Summary", ""]
    for key, value in summary.items():
        if isinstance(value, dict):
            lines.append(f"## {key}")
            for child_key, child_value in value.items():
                lines.append(f"- {child_key}: {child_value}")
        else:
            lines.append(f"- {key}: {value}")
    (out_dir / f"{name}_Summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_ncc(size: int = 1024, target_fpr: float = 1e-6, limit_queries: int | None = None) -> int:
    """每台设备取 1 个 query，独立运行 NCC 指标。"""
    started = time.perf_counter()
    size = int(size)
    out_dir = Path(PRNU_MATCHING_DIR) / f"ncc_size_{size}_one_per_device"
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_paths, query_paths = _load_current_ref_query_paths(size, "one-per-device", limit_queries)

    print("=" * 68)
    print("NCC matching")
    print(f"Size: {size}")
    print("Query policy: one-per-device")
    print(f"Reference: {len(ref_paths)} | Query: {len(query_paths)}")
    print(f"Target FPR: {target_fpr:g}")
    print(f"Output: {out_dir}")
    print("=" * 68)

    ref_names = [path.stem for path in ref_paths]
    query_names = [path.stem for path in query_paths]
    ref_vectors = []
    ref_shape = None
    for idx, ref_path in enumerate(ref_paths, start=1):
        vec, shape = _load_normalized_vector(ref_path)
        if ref_shape is None:
            ref_shape = shape
        elif shape != ref_shape:
            raise ValueError(f"{ref_path.name}: shape {shape} != reference shape {ref_shape}")
        ref_vectors.append(vec)
        if idx % 20 == 0 or idx == len(ref_paths):
            print(f"  loaded refs {idx}/{len(ref_paths)}")
    ref_bank = np.vstack(ref_vectors).astype(np.float32, copy=False)

    scores = np.empty((len(query_paths), len(ref_paths)), dtype=np.float32)
    for qi, query_path in enumerate(query_paths, start=1):
        q_vec, q_shape = _load_normalized_vector(query_path)
        if q_shape != ref_shape:
            raise ValueError(f"{query_path.name}: shape {q_shape} != reference shape {ref_shape}")
        scores[qi - 1, :] = ref_bank @ q_vec
        if qi % 20 == 0 or qi == len(query_paths):
            print(f"  NCC query {qi}/{len(query_paths)}")

    negative_scores = [
        float(scores[qi, ri])
        for qi, query_name in enumerate(query_names)
        for ri, ref_name in enumerate(ref_names)
        if ref_name != _device_from_query_stem(query_name)
    ]
    threshold, allowed_fp = _threshold_for_target_fpr(np.asarray(negative_scores), target_fpr)
    top1 = _top1_metrics(scores, ref_names, query_names)
    fpr_metrics = _verification_metrics(scores, ref_names, query_names, threshold)

    np.save(out_dir / "NCC_Scores.npy", scores)
    _write_lines(out_dir / "Reference_Names.txt", ref_names)
    _write_lines(out_dir / "Query_Names.txt", query_names)
    _write_top1_csv(out_dir / "NCC_Top1.csv", top1["rows"], "ncc")
    _write_pair_csv(out_dir / "NCC_Pair_Scores.csv", scores, ref_names, query_names, "ncc")

    summary = {
        "size": size,
        "query_policy": "one-per-device",
        "reference_count": len(ref_paths),
        "query_count": len(query_paths),
        "top1_accuracy": top1["accuracy"],
        "target_fpr": float(target_fpr),
        "fpr_threshold": threshold,
        "allowed_false_positives": allowed_fp,
        "empirical_resolution": 1 / fpr_metrics["negative_count"] if fpr_metrics["negative_count"] else None,
        "fpr_metrics": fpr_metrics,
        "elapsed_seconds": time.perf_counter() - started,
    }
    _write_summary(out_dir, "NCC", summary)
    print(f"NCC Top-1: {top1['accuracy']:.4%}")
    print(f"NCC TPR@FPR<={target_fpr:g}: {fpr_metrics['tpr']:.4%} | empirical FPR={fpr_metrics['fpr']:.8%}")
    print(f"Saved to: {out_dir}")
    return 0


def run_pce(
    size: int = 1024,
    fixed_threshold: float = 60.0,
    target_fpr: float = 1e-6,
    limit_queries: int | None = None,
) -> int:
    """每台设备取 1 个 query，独立运行全库 PCE 指标。"""
    started = time.perf_counter()
    size = int(size)
    out_dir = Path(PRNU_MATCHING_DIR) / f"pce_size_{size}_one_per_device"
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_paths, query_paths = _load_current_ref_query_paths(size, "one-per-device", limit_queries)

    print("=" * 68)
    print("PCE matching")
    print(f"Size: {size}")
    print("Query policy: one-per-device")
    print(f"Reference: {len(ref_paths)} | Query: {len(query_paths)}")
    print(f"Fixed threshold: {fixed_threshold:g} | Target FPR: {target_fpr:g}")
    print(f"Output: {out_dir}")
    print("=" * 68)

    ref_names = [path.stem for path in ref_paths]
    query_names = [path.stem for path in query_paths]
    ref_shape = None
    ref_ffts = []
    for idx, ref_path in enumerate(ref_paths, start=1):
        ref_vec, shape = _load_normalized_vector(ref_path)
        if ref_shape is None:
            ref_shape = shape
        elif shape != ref_shape:
            raise ValueError(f"{ref_path.name}: shape {shape} != reference shape {ref_shape}")
        ref_ffts.append(np.fft.fft2(ref_vec.reshape(shape)).astype(np.complex64))
        if idx % 20 == 0 or idx == len(ref_paths):
            print(f"  prepared ref FFT {idx}/{len(ref_paths)}")

    scores = np.empty((len(query_paths), len(ref_paths)), dtype=np.float32)
    peaks = np.empty_like(scores)
    with (out_dir / "PCE_Pair_Scores.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["query", "query_device", "reference", "is_match", "pce", "peak", "peak_row", "peak_col"])
        for qi, query_path in enumerate(query_paths):
            query_name = query_names[qi]
            query_device = _device_from_query_stem(query_name)
            q_vec, q_shape = _load_normalized_vector(query_path)
            if q_shape != ref_shape:
                raise ValueError(f"{query_path.name}: shape {q_shape} != reference shape {ref_shape}")
            q_fft = np.fft.fft2(q_vec.reshape(ref_shape)).astype(np.complex64)
            for ri, ref_name in enumerate(ref_names):
                corr = np.fft.ifft2(q_fft * np.conj(ref_ffts[ri])).real.astype(np.float32, copy=False)
                pce, peak, peak_pos = _pce_from_corr(corr)
                scores[qi, ri] = pce
                peaks[qi, ri] = peak
                writer.writerow(
                    [
                        query_name,
                        query_device,
                        ref_name,
                        int(ref_name == query_device),
                        f"{pce:.6f}",
                        f"{peak:.10f}",
                        peak_pos[0],
                        peak_pos[1],
                    ]
                )
            if qi + 1 == len(query_paths) or (qi + 1) % 10 == 0:
                elapsed = time.perf_counter() - started
                print(f"  PCE query {qi + 1}/{len(query_paths)} | elapsed={elapsed:.1f}s")

    negative_scores = [
        float(scores[qi, ri])
        for qi, query_name in enumerate(query_names)
        for ri, ref_name in enumerate(ref_names)
        if ref_name != _device_from_query_stem(query_name)
    ]
    fpr_threshold, allowed_fp = _threshold_for_target_fpr(np.asarray(negative_scores), target_fpr)
    fixed_metrics = _verification_metrics(scores, ref_names, query_names, fixed_threshold)
    fpr_metrics = _verification_metrics(scores, ref_names, query_names, fpr_threshold)
    top1 = _top1_metrics(scores, ref_names, query_names)

    np.save(out_dir / "PCE_Scores.npy", scores)
    np.save(out_dir / "PCE_Peaks.npy", peaks)
    _write_lines(out_dir / "Reference_Names.txt", ref_names)
    _write_lines(out_dir / "Query_Names.txt", query_names)
    _write_top1_csv(out_dir / "PCE_Top1.csv", top1["rows"], "pce")

    summary = {
        "size": size,
        "query_policy": "one-per-device",
        "reference_count": len(ref_paths),
        "query_count": len(query_paths),
        "top1_accuracy": top1["accuracy"],
        "fixed_threshold": float(fixed_threshold),
        "fixed_threshold_metrics": fixed_metrics,
        "target_fpr": float(target_fpr),
        "fpr_threshold": fpr_threshold,
        "allowed_false_positives": allowed_fp,
        "empirical_resolution": 1 / fpr_metrics["negative_count"] if fpr_metrics["negative_count"] else None,
        "fpr_metrics": fpr_metrics,
        "elapsed_seconds": time.perf_counter() - started,
    }
    _write_summary(out_dir, "PCE", summary)
    print(f"PCE Top-1: {top1['accuracy']:.4%}")
    print(f"PCE TPR@threshold={fixed_threshold:g}: {fixed_metrics['tpr']:.4%} | FPR={fixed_metrics['fpr']:.8%}")
    print(f"PCE TPR@FPR<={target_fpr:g}: {fpr_metrics['tpr']:.4%} | empirical FPR={fpr_metrics['fpr']:.8%}")
    print(f"Saved to: {out_dir}")
    return 0


def run_ncc_pce(
    size: int = 1024,
    top_k: int = 5,
    pce_top_k: int = 1,
    limit_queries: int | None = None,
    query_policy: str = "one-per-device",
) -> int:
    """运行 NCC 匹配，并对 NCC Top-K 候选计算 PCE。

    输出目录：
        Outputs/prnu/matching/ncc_pce_size_<size>_<query_policy>/
    """
    size = int(size)
    top_k = max(int(top_k), 1)
    pce_top_k = max(int(pce_top_k), 0)
    if pce_top_k:
        top_k = max(top_k, pce_top_k)

    ref_dir, query_dir = _dirs_for_size(size)
    safe_policy = query_policy.replace("-", "_")
    out_dir = Path(PRNU_MATCHING_DIR) / f"ncc_pce_size_{size}_{safe_policy}"
    out_dir.mkdir(parents=True, exist_ok=True)

    ref_paths = sorted(ref_dir.glob("*.npy"))
    query_paths = sorted(query_dir.glob("*.npy"))
    active_query_stems = _active_query_stems(size)
    if active_query_stems:
        before_count = len(query_paths)
        query_paths = [path for path in query_paths if path.stem in active_query_stems]
        ignored_count = before_count - len(query_paths)
        if ignored_count:
            print(f"[INFO] Ignored {ignored_count} stale query PRNU files not present in current Dataset_query_cropped.")
    query_paths = _select_query_paths(query_paths, query_policy)
    if limit_queries is not None:
        query_paths = query_paths[: int(limit_queries)]

    if not ref_paths:
        raise FileNotFoundError(f"Reference PRNU not found: {ref_dir}")
    if not query_paths:
        raise FileNotFoundError(f"Query PRNU not found: {query_dir}")

    started = time.perf_counter()
    print("=" * 68)
    print("NCC/PCE matching")
    print(f"Size: {size}")
    print(f"Query policy: {query_policy}")
    print(f"Reference: {len(ref_paths)} | Query: {len(query_paths)}")
    print(f"NCC Top-K: {top_k} | PCE Top-K: {pce_top_k}")
    print(f"Output: {out_dir}")
    print("=" * 68)

    ref_names = [p.stem for p in ref_paths]
    query_names = [p.stem for p in query_paths]

    print("[1/3] Loading and normalizing reference PRNU...")
    ref_vectors = []
    ref_shape = None
    for idx, path in enumerate(ref_paths, start=1):
        vec, shape = _load_normalized_vector(path)
        if ref_shape is None:
            ref_shape = shape
        elif shape != ref_shape:
            raise ValueError(f"{path.name}: shape {shape} != reference shape {ref_shape}")
        ref_vectors.append(vec)
        if idx % 20 == 0 or idx == len(ref_paths):
            print(f"  loaded refs {idx}/{len(ref_paths)}")
    ref_bank = np.vstack(ref_vectors).astype(np.float32, copy=False)
    del ref_vectors

    print("[2/3] Computing all-pair NCC...")
    ncc_scores = np.empty((len(query_paths), len(ref_paths)), dtype=np.float32)
    for idx, query_path in enumerate(query_paths):
        q_vec, q_shape = _load_normalized_vector(query_path)
        if q_shape != ref_shape:
            raise ValueError(f"{query_path.name}: shape {q_shape} != reference shape {ref_shape}")
        ncc_scores[idx, :] = ref_bank @ q_vec
        if (idx + 1) % 200 == 0 or idx + 1 == len(query_paths):
            elapsed = time.perf_counter() - started
            print(f"  NCC query {idx + 1}/{len(query_paths)} | elapsed={elapsed:.1f}s")

    np.save(out_dir / "NCC_Scores.npy", ncc_scores)
    _write_lines(out_dir / "Reference_Names.txt", ref_names)
    _write_lines(out_dir / "Query_Names.txt", query_names)

    # 排序时先 argpartition 再局部排序，避免对每行完整排序。
    k = min(top_k, len(ref_names))
    top_unsorted = np.argpartition(-ncc_scores, kth=k - 1, axis=1)[:, :k]
    top_order = np.take_along_axis(ncc_scores, top_unsorted, axis=1).argsort(axis=1)[:, ::-1]
    top_indices = np.take_along_axis(top_unsorted, top_order, axis=1)

    top1_ok = 0
    top5_ok = 0
    with (out_dir / "NCC_TopK.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["query", "query_device", "rank", "reference", "is_match", "ncc"])
        for qi, q_name in enumerate(query_names):
            q_dev = _device_from_query_stem(q_name)
            refs_for_query = [ref_names[int(ri)] for ri in top_indices[qi]]
            if refs_for_query and refs_for_query[0] == q_dev:
                top1_ok += 1
            if q_dev in refs_for_query[: min(5, len(refs_for_query))]:
                top5_ok += 1
            for rank, ri in enumerate(top_indices[qi], start=1):
                ref_name = ref_names[int(ri)]
                writer.writerow(
                    [
                        q_name,
                        q_dev,
                        rank,
                        ref_name,
                        int(ref_name == q_dev),
                        f"{float(ncc_scores[qi, int(ri)]):.10f}",
                    ]
                )

    pce_top1_ok = None
    pce_rows = 0
    if pce_top_k > 0:
        print("[3/3] Computing PCE for NCC candidates...")
        ref_ffts = []
        for idx in range(len(ref_names)):
            ref_img = ref_bank[idx].reshape(ref_shape)
            ref_ffts.append(np.fft.fft2(ref_img).astype(np.complex64))
            if (idx + 1) % 20 == 0 or idx + 1 == len(ref_names):
                print(f"  prepared ref FFT {idx + 1}/{len(ref_names)}")
        del ref_bank

        pce_top1_ok = 0
        pce_k = min(pce_top_k, top_indices.shape[1])
        with (out_dir / "PCE_TopK.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "query",
                    "query_device",
                    "ncc_rank",
                    "reference",
                    "is_match",
                    "ncc",
                    "pce",
                    "peak",
                    "peak_row",
                    "peak_col",
                ]
            )
            for qi, query_path in enumerate(query_paths):
                q_name = query_names[qi]
                q_dev = _device_from_query_stem(q_name)
                q_vec, _ = _load_normalized_vector(query_path)
                q_fft = np.fft.fft2(q_vec.reshape(ref_shape)).astype(np.complex64)
                scored = []
                for rank_idx, ri in enumerate(top_indices[qi, :pce_k], start=1):
                    ri = int(ri)
                    corr = np.fft.ifft2(q_fft * np.conj(ref_ffts[ri])).real.astype(np.float32, copy=False)
                    pce, peak, peak_pos = _pce_from_corr(corr)
                    scored.append((pce, rank_idx, ri, peak, peak_pos))
                    writer.writerow(
                        [
                            q_name,
                            q_dev,
                            rank_idx,
                            ref_names[ri],
                            int(ref_names[ri] == q_dev),
                            f"{float(ncc_scores[qi, ri]):.10f}",
                            f"{pce:.6f}",
                            f"{peak:.10f}",
                            peak_pos[0],
                            peak_pos[1],
                        ]
                    )
                    pce_rows += 1
                if scored:
                    best = max(scored, key=lambda item: item[0])
                    if ref_names[best[2]] == q_dev:
                        pce_top1_ok += 1
                if (qi + 1) % 100 == 0 or qi + 1 == len(query_paths):
                    elapsed = time.perf_counter() - started
                    print(f"  PCE query {qi + 1}/{len(query_paths)} | elapsed={elapsed:.1f}s")
    else:
        print("[3/3] PCE skipped because --pce-top-k=0")

    elapsed = time.perf_counter() - started
    summary = {
        "size": size,
        "reference_count": len(ref_paths),
        "query_count": len(query_paths),
        "query_policy": query_policy,
        "top_k": top_k,
        "pce_top_k": pce_top_k,
        "ncc_top1_accuracy": top1_ok / len(query_paths),
        "ncc_top5_accuracy": top5_ok / len(query_paths),
        "pce_top1_accuracy_within_ncc_candidates": None
        if pce_top1_ok is None
        else pce_top1_ok / len(query_paths),
        "pce_rows": pce_rows,
        "elapsed_seconds": elapsed,
        "outputs": {
            "ncc_scores": str(out_dir / "NCC_Scores.npy"),
            "ncc_topk": str(out_dir / "NCC_TopK.csv"),
            "pce_topk": str(out_dir / "PCE_TopK.csv") if pce_top_k > 0 else None,
        },
    }
    (out_dir / "Summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "Summary.md").write_text(
        "\n".join(
            [
                "# NCC/PCE Matching Summary",
                "",
                f"- Size: {size}",
                f"- Query policy: {query_policy}",
                f"- Reference count: {len(ref_paths)}",
                f"- Query count: {len(query_paths)}",
                f"- NCC Top-1: {summary['ncc_top1_accuracy']:.4%}",
                f"- NCC Top-5: {summary['ncc_top5_accuracy']:.4%}",
                f"- PCE Top-1 within NCC candidates: "
                + (
                    "N/A"
                    if summary["pce_top1_accuracy_within_ncc_candidates"] is None
                    else f"{summary['pce_top1_accuracy_within_ncc_candidates']:.4%}"
                ),
                f"- Elapsed seconds: {elapsed:.2f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 68)
    print(f"NCC Top-1: {summary['ncc_top1_accuracy']:.4%}")
    print(f"NCC Top-5: {summary['ncc_top5_accuracy']:.4%}")
    if summary["pce_top1_accuracy_within_ncc_candidates"] is not None:
        print(f"PCE Top-1 within NCC candidates: {summary['pce_top1_accuracy_within_ncc_candidates']:.4%}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Saved to: {out_dir}")
    print("=" * 68)
    return 0

from __future__ import annotations

import argparse
import mimetypes
import random
import re
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image


BRAND_MAP = {
    "Apple": "苹果",
    "Asus": "华硕",
    "Huawei": "华为",
    "Lenovo": "联想",
    "LG": "LG",
    "Microsoft": "微软",
    "OnePlus": "一加",
    "Samsung": "三星",
    "Sony": "索尼",
    "Wiko": "维科",
    "Xiaomi": "小米",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".JPG", ".JPEG"}
MIN_IMAGE_SIDE = 1024


@dataclass(frozen=True)
class DeviceImportPlan:
    dataset_index: int
    source_dir: Path
    source_brand: str
    brand: str
    model: str
    notes: str
    selected_bucket: str
    selected_orientation: str
    candidate_count: int
    build_files: list[Path]
    skipped_reason: str | None = None


def natural_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def random_mac() -> str:
    octets = [0x02] + [random.SystemRandom().randrange(0, 256) for _ in range(5)]
    return ":".join(f"{value:02X}" for value in octets)


def parse_device_dir(path: Path) -> tuple[int, str, str] | None:
    match = re.match(r"D(\d+)_(.+?)_(.+)$", path.name)
    if match is None:
        return None
    return int(match.group(1)), match.group(2), match.group(3)


def is_usable_landscape(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            width, height = image.size
        return width >= height and min(width, height) >= MIN_IMAGE_SIDE
    except (OSError, ValueError):
        return False


def image_files_in(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(
        [item for item in path.iterdir() if item.is_file() and item.suffix in IMAGE_EXTENSIONS],
        key=natural_key,
    )


def landscape_images_in(path: Path) -> list[Path]:
    return [item for item in image_files_in(path) if is_usable_landscape(item)]


def is_decodable(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.load()
        return True
    except (OSError, ValueError):
        return False


def decodable_files(files: list[Path]) -> tuple[list[Path], list[Path]]:
    valid: list[Path] = []
    invalid: list[Path] = []
    for path in files:
        if is_decodable(path):
            valid.append(path)
        else:
            invalid.append(path)
    return valid, invalid


def build_import_plans(dataset_root: Path) -> list[DeviceImportPlan]:
    plans: list[DeviceImportPlan] = []
    for device_dir in sorted([item for item in dataset_root.iterdir() if item.is_dir()], key=natural_key):
        parsed = parse_device_dir(device_dir)
        if parsed is None:
            continue

        dataset_index, source_brand, model = parsed
        brand = BRAND_MAP.get(source_brand, source_brand)
        notes = f"VISION数据集设备{dataset_index}"
        selected_files = landscape_images_in(device_dir / "images" / "flat" / "0")
        build_files = selected_files[:-5] if len(selected_files) > 5 else []
        skipped_reason = None if build_files else f"可用横向参考图不足或最小边小于{MIN_IMAGE_SIDE}，留下后5张后无建库图像"
        plans.append(
            DeviceImportPlan(
                dataset_index=dataset_index,
                source_dir=device_dir,
                source_brand=source_brand,
                brand=brand,
                model=model,
                notes=notes,
                selected_bucket="0",
                selected_orientation="横向",
                candidate_count=len(selected_files),
                build_files=build_files,
                skipped_reason=skipped_reason,
            )
        )
    return plans


def fetch_json(client: httpx.Client, path: str):
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def existing_state(client: httpx.Client) -> tuple[dict[str, dict], set[str]]:
    devices = fetch_json(client, "/devices")
    fingerprints = fetch_json(client, "/fingerprints")
    devices_by_note = {row.get("notes"): row for row in devices if row.get("notes")}
    fingerprint_notes = {
        (row.get("device") or {}).get("notes")
        for row in fingerprints
        if (row.get("device") or {}).get("notes")
    }
    return devices_by_note, fingerprint_notes


def create_device(client: httpx.Client, plan: DeviceImportPlan) -> dict:
    response = client.post(
        "/devices",
        json={
            "brand": plan.brand,
            "model": plan.model,
            "mac_address": random_mac(),
            "notes": plan.notes,
        },
    )
    response.raise_for_status()
    return response.json()


def submit_build_job(client: httpx.Client, device_id: int, files: list[Path]) -> dict:
    with ExitStack() as stack:
        upload_files = []
        for path in files:
            content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            upload_files.append(("files", (path.name, stack.enter_context(path.open("rb")), content_type)))
        response = client.post(
            "/fingerprints/build",
            data={"device_id": str(device_id)},
            files=upload_files,
        )
    response.raise_for_status()
    return response.json()


def wait_for_job(client: httpx.Client, job_id: int, poll_seconds: float = 2.0) -> dict:
    while True:
        job = fetch_json(client, f"/jobs/{job_id}")
        status = job.get("status")
        if status == "succeeded":
            return job
        if status == "failed":
            raise RuntimeError(job.get("error") or f"任务 {job_id} 失败")
        time.sleep(poll_seconds)


def print_plan(plans: list[DeviceImportPlan], devices_by_note: dict[str, dict], fingerprint_notes: set[str]) -> None:
    print("idx,目录,状态,品牌,型号,选择目录,方向,候选数,建库数,首张,末张")
    for plan in plans:
        if plan.skipped_reason:
            status = f"跳过：{plan.skipped_reason}"
        elif plan.notes in fingerprint_notes:
            status = "已存在指纹"
        elif plan.notes in devices_by_note:
            status = "已存在设备，待补建指纹"
        else:
            status = "待导入"
        first_file = plan.build_files[0].name if plan.build_files else "-"
        last_file = plan.build_files[-1].name if plan.build_files else "-"
        print(
            ",".join(
                [
                    f"D{plan.dataset_index:02d}",
                    plan.source_dir.name,
                    status,
                    plan.brand,
                    plan.model,
                    plan.selected_bucket,
                    plan.selected_orientation,
                    str(plan.candidate_count),
                    str(len(plan.build_files)),
                    first_file,
                    last_file,
                ]
            )
        )


def run_import(args: argparse.Namespace) -> int:
    dataset_root = Path(args.dataset).resolve()
    if not dataset_root.exists():
        raise FileNotFoundError(f"数据集目录不存在：{dataset_root}")

    plans = build_import_plans(dataset_root)
    timeout = httpx.Timeout(None, connect=20.0)
    with httpx.Client(base_url=args.api.rstrip("/"), timeout=timeout) as client:
        devices_by_note, fingerprint_notes = existing_state(client)
        print_plan(plans, devices_by_note, fingerprint_notes)
        if not args.apply:
            print("DRY_RUN: 未执行导入。加 --apply 后开始提交。")
            return 0

        imported = 0
        skipped = 0
        for plan in plans:
            if plan.skipped_reason or plan.notes in fingerprint_notes:
                skipped += 1
                continue

            build_files, invalid_files = decodable_files(plan.build_files)
            if invalid_files:
                print(
                    f"D{plan.dataset_index:02d} 剔除无法完整解码图片 {len(invalid_files)} 张："
                    + "、".join(path.name for path in invalid_files[:8])
                    + ("..." if len(invalid_files) > 8 else "")
                )
            if not build_files:
                print(f"跳过 D{plan.dataset_index:02d}: 剔除坏图后无可用建库图像")
                skipped += 1
                continue

            device = devices_by_note.get(plan.notes)
            if device is None:
                device = create_device(client, plan)
                devices_by_note[plan.notes] = device
                print(f"已创建设备 D{plan.dataset_index:02d}: {device['name']}")
            else:
                print(f"复用已有设备 D{plan.dataset_index:02d}: {device['name']}")

            payload = submit_build_job(client, int(device["id"]), build_files)
            job_id = int(payload["job_id"])
            print(f"已提交建库任务 D{plan.dataset_index:02d}: job_id={job_id}, images={len(build_files)}")
            if args.wait:
                job = wait_for_job(client, job_id)
                print(f"建库完成 D{plan.dataset_index:02d}: job_id={job_id}, progress={job.get('progress')}")
                fingerprint_notes.add(plan.notes)
            imported += 1

        print(f"导入提交完成：新增/补建 {imported} 台，跳过 {skipped} 台")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="批量导入 VISION flat/0 横向参考图并构建设备指纹")
    parser.add_argument("--dataset", default=r"F:\ExpDataset\VISION\dataset", help="VISION dataset 根目录")
    parser.add_argument("--api", default="http://localhost:8000", help="后端 API 地址")
    parser.add_argument("--apply", action="store_true", help="实际提交导入；默认只预演")
    parser.add_argument("--wait", action="store_true", help="每个构建任务提交后等待完成再继续")
    args = parser.parse_args()
    return run_import(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

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
    "BQ": "BQ",
    "Google": "谷歌",
    "Huawei": "华为",
    "LG": "LG",
    "Motorola": "摩托罗拉",
    "Samsung": "三星",
    "Sony": "索尼",
    "Wiko": "维科",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".JPG", ".JPEG"}


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


def image_orientation(path: Path) -> str:
    with Image.open(path) as image:
        width, height = image.size
    return "横向" if width >= height else "竖向"


def image_files_in(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(
        [item for item in path.iterdir() if item.is_file() and item.suffix in IMAGE_EXTENSIONS],
        key=natural_key,
    )


def choose_orig_bucket(orig_root: Path) -> tuple[str, list[Path]]:
    if not orig_root.exists():
        return "-", []

    files = image_files_in(orig_root / "0")
    if files:
        return "0", files
    return "0", []


def choose_orientation(files: list[Path]) -> tuple[str, list[Path]]:
    by_orientation = {"横向": [], "竖向": []}
    for path in files:
        by_orientation[image_orientation(path)].append(path)
    orientation, selected = max(by_orientation.items(), key=lambda item: (len(item[1]), item[0] == "横向"))
    return orientation, sorted(selected, key=natural_key)


def build_import_plans(dataset_root: Path) -> list[DeviceImportPlan]:
    plans: list[DeviceImportPlan] = []
    for device_dir in sorted([item for item in dataset_root.iterdir() if item.is_dir()]):
        parsed = parse_device_dir(device_dir)
        if parsed is None:
            continue

        dataset_index, source_brand, model = parsed
        brand = BRAND_MAP.get(source_brand, source_brand)
        notes = f"FODB数据集设备{dataset_index}"
        bucket_name, bucket_files = choose_orig_bucket(device_dir / "orig")
        orientation, selected_files = choose_orientation(bucket_files) if bucket_files else ("-", [])
        build_files = selected_files[:-5] if len(selected_files) > 5 else []
        skipped_reason = None if build_files else "可用参考图不足，留下后5张后无建库图像"
        plans.append(
            DeviceImportPlan(
                dataset_index=dataset_index,
                source_dir=device_dir,
                source_brand=source_brand,
                brand=brand,
                model=model,
                notes=notes,
                selected_bucket=bucket_name,
                selected_orientation=orientation,
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

            device = devices_by_note.get(plan.notes)
            if device is None:
                device = create_device(client, plan)
                devices_by_note[plan.notes] = device
                print(f"已创建设备 D{plan.dataset_index:02d}: {device['name']}")
            else:
                print(f"复用已有设备 D{plan.dataset_index:02d}: {device['name']}")

            payload = submit_build_job(client, int(device["id"]), plan.build_files)
            job_id = int(payload["job_id"])
            print(f"已提交建库任务 D{plan.dataset_index:02d}: job_id={job_id}, images={len(plan.build_files)}")
            if args.wait:
                job = wait_for_job(client, job_id)
                print(f"建库完成 D{plan.dataset_index:02d}: job_id={job_id}, progress={job.get('progress')}")
                fingerprint_notes.add(plan.notes)
            imported += 1

        print(f"导入提交完成：新增/补建 {imported} 台，跳过 {skipped} 台")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="批量导入 FODB orig 参考图并构建设备指纹")
    parser.add_argument("--dataset", default=r"F:\ExpDataset\FODB", help="FODB 根目录")
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

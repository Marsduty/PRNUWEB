from datetime import date, datetime, time, timedelta
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.routes.serializers import comparison_decision, device_to_summary, visible_comparison_rows
from app.models.comparison_result import ComparisonResult
from app.models.fingerprint import Fingerprint
from app.models.job import Job

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _percent_change(current: int, previous: int) -> float:
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round(((current - previous) / previous) * 100, 2)


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    today_start = datetime.combine(date.today(), time.min)
    yesterday_start = today_start - timedelta(days=1)
    image_count = db.query(Fingerprint).count()
    today_uploads = db.query(Fingerprint).filter(Fingerprint.created_at >= today_start).count()
    today_jobs = db.query(Job).filter(Job.created_at >= today_start).count()
    today_hits = (
        db.query(ComparisonResult)
        .filter(ComparisonResult.created_at >= today_start)
        .filter(ComparisonResult.is_hit.is_(True))
        .count()
    )
    yesterday_image_count = db.query(Fingerprint).filter(Fingerprint.created_at < today_start).count()
    yesterday_uploads = (
        db.query(Fingerprint)
        .filter(Fingerprint.created_at >= yesterday_start)
        .filter(Fingerprint.created_at < today_start)
        .count()
    )
    yesterday_jobs = (
        db.query(Job)
        .filter(Job.created_at >= yesterday_start)
        .filter(Job.created_at < today_start)
        .count()
    )
    yesterday_hits = (
        db.query(ComparisonResult)
        .filter(ComparisonResult.created_at >= yesterday_start)
        .filter(ComparisonResult.created_at < today_start)
        .filter(ComparisonResult.is_hit.is_(True))
        .count()
    )
    distribution_counter: Counter[str] = Counter()
    for fingerprint in db.query(Fingerprint).all():
        device = fingerprint.device
        label = device.brand if device is not None and device.brand else "未标注品牌"
        distribution_counter[label] += 1

    recent_comparison_jobs = (
        db.query(Job)
        .filter(Job.type.in_(["database_comparison", "external_comparison"]))
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(20)
        .all()
    )
    recent_job_ids = [job.id for job in recent_comparison_jobs]
    raw_recent_results = []
    if recent_job_ids:
        raw_recent_results = (
            db.query(ComparisonResult)
            .filter(ComparisonResult.job_id.in_(recent_job_ids))
            .order_by(ComparisonResult.job_id.asc(), ComparisonResult.rank.asc())
            .all()
        )
    grouped_results: dict[int, list[ComparisonResult]] = {}
    for row in raw_recent_results:
        if row.job_id not in grouped_results:
            grouped_results[row.job_id] = []
        grouped_results[row.job_id].append(row)

    recent_results: list[ComparisonResult] = []
    for job in recent_comparison_jobs:
        job_id = job.id
        rows = sorted(grouped_results.get(job_id, []), key=lambda row: row.rank or 0)
        recent_results.extend(visible_comparison_rows(rows))
        if len(recent_results) >= 8:
            break
    recent_results = recent_results[:8]

    return {
        "image_count": image_count,
        "today_uploads": today_uploads,
        "today_comparisons": today_jobs,
        "today_hits": today_hits,
        "metric_trends": {
            "image_count": {
                "previous": yesterday_image_count,
                "percent_change": _percent_change(image_count, yesterday_image_count),
            },
            "today_uploads": {
                "previous": yesterday_uploads,
                "percent_change": _percent_change(today_uploads, yesterday_uploads),
            },
            "today_comparisons": {
                "previous": yesterday_jobs,
                "percent_change": _percent_change(today_jobs, yesterday_jobs),
            },
            "today_hits": {
                "previous": yesterday_hits,
                "percent_change": _percent_change(today_hits, yesterday_hits),
            },
        },
        "device_distribution": [
            {"name": name, "value": count}
            for name, count in distribution_counter.most_common()
        ],
        "recent_results": [
            {
                "id": row.id,
                "job_id": row.job_id,
                "comparison_type": row.comparison_type,
                "decision": comparison_decision(row),
                "pce": row.pce,
                "is_hit": row.is_hit,
                "created_at": row.created_at,
                "device": device_to_summary(row.candidate_device),
            }
            for row in recent_results
        ],
    }

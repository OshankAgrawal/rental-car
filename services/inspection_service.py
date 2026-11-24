import json
import math
import uuid
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from models import Detection, Inspection, Rental, Report, Video
from services.video_service import analyze_video


def validate_video_upload(filename, content_type, allowed_extensions, allowed_types):
    extension = Path(filename or "").suffix.lower()
    if extension not in allowed_extensions:
        raise ValueError("Unsupported video format")
    if content_type and content_type not in allowed_types:
        raise ValueError("Unsupported video format")
    return extension


async def save_and_analyze_video(
    db: Session,
    rental: Rental,
    inspection: Inspection,
    upload,
    upload_dir: Path,
    detected_frames_dir: Path,
    detection_json_dir: Path,
    on_progress=None,
):
    extension = Path(upload.filename).suffix.lower()
    stored_path = upload_dir / f"{uuid.uuid4().hex}{extension}"
    try:
        with stored_path.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                output.write(chunk)

        video = Video(
            inspection_id=inspection.id,
            original_filename=Path(upload.filename).name,
            stored_path=str(stored_path),
            mime_type=upload.content_type,
            file_size_bytes=stored_path.stat().st_size,
        )
        db.add(video)
        inspection.status = "processing"
        db.flush()

        output_dir = detected_frames_dir / str(rental.id) / inspection.inspection_type
        analysis = await run_in_threadpool(
            analyze_video,
            stored_path,
            output_dir,
            on_progress,
        )
        json_path = detection_json_dir / f"{rental.id}_{inspection.inspection_type}.json"
        Path(analysis["json_path"]).replace(json_path)
        analysis["json_path"] = str(json_path)
        inspection.detection_json_path = analysis["json_path"]
        inspection.status = "completed"
        video.duration_seconds = analysis["duration_seconds"]

        detections = []
        for item in analysis["detections"]:
            detection = Detection(
                inspection_id=inspection.id,
                frame_number=item["frame_number"],
                timestamp_seconds=item["timestamp_seconds"],
                class_name=item["damage_type"],
                confidence=item["confidence"],
                bbox_xyxy=item["bbox_xyxy"],
                segmentation_polygon=item["segmentation_polygon"],
                defect_frame_path=item["defect_frame_path"],
            )
            db.add(detection)
            detections.append(detection)

        db.flush()
        return detections
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise


def create_pickup_report(
    db: Session,
    rental: Rental,
    inspection: Inspection,
    detections,
    reports_dir: Path,
    detected_frames_dir: Path,
):
    report_data = {
        "report_type": "pickup_inspection",
        "rental_information": {
            "rental_id": rental.rental_id,
            "vehicle_registration": rental.vehicle_registration,
            "customer": {
                "name": rental.customer_name,
                "phone": rental.customer_phone,
            },
        },
        "pickup_inspection": {
            "date_and_time": inspection.inspection_time.isoformat(),
            "detection_json": inspection.detection_json_path,
            "detection_count": len(detections),
            "frames": [
                {
                    "frame_number": detection.frame_number,
                    "timestamp_seconds": detection.timestamp_seconds,
                    "damage_type": detection.class_name,
                    "confidence": detection.confidence,
                    "frame_url": frame_url(
                        detection.defect_frame_path,
                        detected_frames_dir,
                    ),
                }
                for detection in detections
            ],
        },
    }
    report_path = reports_dir / f"{rental.id}_pickup_inspection.json"
    report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    db.add(Report(
        rental_id=rental.rental_id,
        report_type="pickup_inspection",
        file_path=str(report_path),
    ))
    return report_data


def box_area(box):
    if not box or len(box) != 4:
        return 0.0
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def box_overlap(first, second):
    if not first or not second or len(first) != 4 or len(second) != 4:
        return 0.0
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = box_area(first) + box_area(second) - intersection
    return intersection / union if union else 0.0


def group_damage_detections(detections):
    groups = []
    for detection in sorted(detections, key=lambda item: item.frame_number):
        matching_group = None
        for group in groups:
            representative = group["representative"]
            if (
                representative.class_name == detection.class_name
                and box_overlap(representative.bbox_xyxy, detection.bbox_xyxy) >= 0.30
            ):
                matching_group = group
                break

        if matching_group is None:
            groups.append({"representative": detection, "detections": [detection]})
        else:
            matching_group["detections"].append(detection)
            if detection.confidence > matching_group["representative"].confidence:
                matching_group["representative"] = detection
    return groups


def compare_damage(pickup_detections, return_detections):
    existing = []
    newly_detected = []
    worsened = []
    matched_pickup_ids = set()
    charge_candidates = []

    pickup_groups = group_damage_detections(pickup_detections)
    return_groups = group_damage_detections(return_detections)

    for return_group in return_groups:
        returned = return_group["representative"]
        matched_group = None
        best_overlap = 0.0
        for pickup_group in pickup_groups:
            pickup = pickup_group["representative"]
            if pickup.class_name != returned.class_name:
                continue
            overlap = box_overlap(pickup.bbox_xyxy, returned.bbox_xyxy)
            if overlap > best_overlap:
                best_overlap = overlap
                matched_group = pickup_group

        item = {
            "detection_id": returned.id,
            "damage_type": returned.class_name,
            "confidence": returned.confidence,
            "frame_path": returned.defect_frame_path,
            "frames": [
                detection.defect_frame_path
                for detection in return_group["detections"]
            ],
        }

        if matched_group is not None and best_overlap >= 0.20:
            matched = matched_group["representative"]
            matched_pickup_ids.add(matched.id)
            existing.append(item)
            pickup_area = box_area(matched.bbox_xyxy)
            return_area = box_area(returned.bbox_xyxy)
            if returned.confidence > matched.confidence or (
                pickup_area > 0 and return_area > pickup_area * 1.15
            ):
                worsened_item = {
                    **item,
                    "pickup_confidence": matched.confidence,
                }
                worsened.append(worsened_item)
                charge_candidates.append({**worsened_item, "reason": "potentially_worsened"})
        else:
            newly_detected.append(item)
            charge_candidates.append({**item, "reason": "newly_detected"})

    no_longer_detected = [
        {
            "damage_type": detection.class_name,
            "confidence": detection.confidence,
            "frame_path": detection.defect_frame_path,
        }
        for group in pickup_groups
        for detection in [group["representative"]]
        if detection.id not in matched_pickup_ids
    ]

    return {
        "existing": existing,
        "newly_detected": newly_detected,
        "worsened": worsened,
        "no_longer_detected": no_longer_detected,
        "charge_candidates": charge_candidates,
    }


def frame_url(frame_path: str, detected_frames_dir: Path):
    relative_path = Path(frame_path).resolve().relative_to(detected_frames_dir.resolve())
    return "/detected_frames/" + relative_path.as_posix()


def serialize_charge_candidates(candidates, detected_frames_dir):
    serialized = []
    for candidate in candidates:
        frame_paths = [candidate["frame_path"]]
        frame_paths.extend(
            path
            for path in candidate["frames"]
            if path != candidate["frame_path"]
        )
        serialized.append({
            **candidate,
            "frame_url": frame_url(candidate["frame_path"], detected_frames_dir),
            "frame_urls": [
                frame_url(path, detected_frames_dir)
                for path in frame_paths[:8]
            ],
        })
    return serialized


def money(value: Decimal):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def finalize_return_report(
    db: Session,
    rental: Rental,
    pickup: Inspection,
    returned: Inspection,
    charge_by_detection_id: dict[int, Decimal],
    reports_dir: Path,
    detected_frames_dir: Path,
):
    pickup_detections = list(pickup.detections)
    return_detections = list(returned.detections)
    comparison = compare_damage(pickup_detections, return_detections)

    expected_ids = {item["detection_id"] for item in comparison["charge_candidates"]}
    if expected_ids != set(charge_by_detection_id):
        raise ValueError("A damage charge must be supplied for each new or worsened damage")

    for detection in return_detections:
        if detection.id in charge_by_detection_id:
            detection.damage_charge = charge_by_detection_id[detection.id]
    damage_charge = sum(charge_by_detection_id.values(), Decimal("0.00"))

    pickup_time = pickup.inspection_time
    return_time = returned.inspection_time
    duration_seconds = max(0.0, (return_time - pickup_time).total_seconds())
    duration_hours = math.ceil(duration_seconds / 3600)
    rental_charge = Decimal(duration_hours) * Decimal("50.00")
    total_charge = rental_charge + damage_charge

    rental.rental_cost = rental_charge
    rental.damage_charge = damage_charge
    rental.total_charge = total_charge

    def report_damage_item(item):
        frame_paths = item.get("frames", [item["frame_path"]])
        return {
            **item,
            "frame_url": frame_url(item["frame_path"], detected_frames_dir),
            "frame_urls": [
                frame_url(path, detected_frames_dir)
                for path in frame_paths[:8]
            ],
        }

    def report_inspection_frames(detections):
        return [
            {
                "frame_number": detection.frame_number,
                "timestamp_seconds": detection.timestamp_seconds,
                "damage_type": detection.class_name,
                "confidence": detection.confidence,
                "frame_url": frame_url(
                    detection.defect_frame_path,
                    detected_frames_dir,
                ),
            }
            for detection in detections
        ]

    return_report_data = {
        "report_type": "return_inspection",
        "rental_information": {
            "rental_id": rental.rental_id,
            "vehicle_registration": rental.vehicle_registration,
            "customer": {
                "name": rental.customer_name,
                "phone": rental.customer_phone,
            },
        },
        "return_inspection": {
            "date_and_time": return_time.isoformat(),
            "detection_json": returned.detection_json_path,
            "detection_count": len(return_detections),
            "frames": report_inspection_frames(return_detections),
        },
        "rental_charge_inr": money(rental_charge),
        "damage_charge_items": [
            {
                "detection_id": detection.id,
                "damage_type": detection.class_name,
                "frame_url": frame_url(
                    detection.defect_frame_path,
                    detected_frames_dir,
                ),
                "amount_inr": money(detection.damage_charge),
            }
            for detection in return_detections
            if detection.damage_charge is not None
        ],
        "damage_charge_total_inr": money(damage_charge),
        "total_charge_inr": money(total_charge),
    }

    report_data = {
        "report_type": "final_comparison",
        "rental_information": {
            "rental_id": rental.rental_id,
            "vehicle_registration": rental.vehicle_registration,
            "customer": {
                "name": rental.customer_name,
                "phone": rental.customer_phone,
            },
        },
        "rental_duration_and_charges": {
            "pickup_date_and_time": pickup_time.isoformat(),
            "return_date_and_time": return_time.isoformat(),
            "total_rental_duration_seconds": round(duration_seconds, 2),
            "total_rental_duration_hours": duration_hours,
            "hourly_rental_charge_inr": "50.00",
            "rental_charge_inr": money(rental_charge),
            "damage_charge_inr": money(damage_charge),
            "total_charge_inr": money(total_charge),
            "damage_charge_items": [
                {
                    "detection_id": detection.id,
                    "damage_type": detection.class_name,
                    "frame_path": detection.defect_frame_path,
                    "frame_url": frame_url(
                        detection.defect_frame_path,
                        detected_frames_dir,
                    ),
                    "amount_inr": money(detection.damage_charge),
                }
                for detection in return_detections
                if detection.damage_charge is not None
            ],
        },
        "vehicle_damage_comparison": {
            "existing_damage_at_pickup": [
                report_damage_item(item) for item in comparison["existing"]
            ],
            "newly_detected_damage": [
                report_damage_item(item) for item in comparison["newly_detected"]
            ],
            "potentially_worsened_damage": [
                report_damage_item(item) for item in comparison["worsened"]
            ],
            "damage_no_longer_detected": [
                report_damage_item(item)
                for item in comparison["no_longer_detected"]
            ],
        },
        "final_inspection_summary": {
            "pickup_inspection": {
                "date_and_time": pickup_time.isoformat(),
                "detection_json": pickup.detection_json_path,
                "detection_count": len(pickup_detections),
                "frames": report_inspection_frames(pickup_detections),
            },
            "return_inspection": {
                "date_and_time": return_time.isoformat(),
                "detection_json": returned.detection_json_path,
                "detection_count": len(return_detections),
                "frames": report_inspection_frames(return_detections),
            },
            "final_damage_summary": {
                "existing_damage_count": len(comparison["existing"]),
                "new_damage_count": len(comparison["newly_detected"]),
                "worsened_damage_count": len(comparison["worsened"]),
                "resolved_damage_count": len(comparison["no_longer_detected"]),
            },
        },
    }

    return_report_path = reports_dir / f"{rental.id}_return_inspection.json"
    return_report_path.write_text(
        json.dumps(return_report_data, indent=2),
        encoding="utf-8",
    )
    db.add(Report(
        rental_id=rental.rental_id,
        report_type="return_inspection",
        file_path=str(return_report_path),
    ))

    report_path = reports_dir / f"{rental.id}_final_comparison.json"
    report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    db.add(Report(
        rental_id=rental.rental_id,
        report_type="final_comparison",
        file_path=str(report_path),
    ))
    db.commit()
    return report_data, {
        "rental_charge": money(rental_charge),
        "damage_charge": money(damage_charge),
        "total_charge": money(total_charge),
        "report_path": str(report_path),
    }

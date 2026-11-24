import json
from pathlib import Path

import cv2
from ultralytics import YOLO

# Local model path
MODEL_PATH = Path(__file__).resolve().parent / "models" / "damage_segmentation.pt"

# Load model once when this module is imported
if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Model not found: {MODEL_PATH}. Run download_model.py first."
    )

model = YOLO(str(MODEL_PATH))


def predict_image(image_path):
    """
    Detect vehicle damage in a single image.
    """

    results = model.predict(
        source=str(image_path),
        imgsz=896,
        conf=0.25,
        save=False,
        verbose=False,
        stream=True
    )

    result = results[0]

    detections = []

    if result.boxes is not None:

        for index, box in enumerate(result.boxes):

            cls = int(box.cls[0])
            confidence = float(box.conf[0])

            detection = {
                "damage_type": model.names[cls],
                "confidence": round(confidence, 4),
                "bbox_xyxy": [
                    round(float(value), 1)
                    for value in box.xyxy[0]
                ],
                "segmentation_polygon": (
                    result.masks.xy[index].tolist()
                    if result.masks is not None and index < len(result.masks.xy)
                    else None
                )
            }

            detections.append(detection)

    return {
        "image": str(image_path),
        "total_detections": len(detections),
        "detections": detections
    }


def process_video(video_path, output_dir, frame_interval_seconds=1.0, on_progress=None):
    """Extract frames and return only frames that contain detected damage."""
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    frame_dir = output_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video_path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, int(round(fps * frame_interval_seconds)))
    total_video_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_video_frames / fps
    total_sampled_frames = max(1, (total_video_frames + frame_interval - 1) // frame_interval)

    detections = []
    frame_number = 0
    processed_sampled_frames = 0

    while capture.isOpened():
        success, frame = capture.read()
        if not success:
            break

        if frame_number % frame_interval == 0:
            results = model.predict(
                source=frame,
                imgsz=896,
                conf=0.25,
                save=False,
                verbose=False,
            )
            result = results[0]

            if result.boxes is not None and len(result.boxes):
                timestamp = frame_number / fps
                frame_name = f"frame_{frame_number:06d}_{timestamp:.2f}s.jpg"
                frame_path = frame_dir / frame_name

                for index, box in enumerate(result.boxes):
                    cls = int(box.cls[0])
                    confidence = float(box.conf[0])
                    x1, y1, x2, y2 = [
                        int(round(float(value)))
                        for value in box.xyxy[0]
                    ]
                    label = f"{model.names[cls]} {confidence:.2f}"
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    cv2.putText(
                        frame,
                        label,
                        (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2,
                    )

                if not cv2.imwrite(str(frame_path), frame):
                    raise OSError(f"Could not save detected frame: {frame_path}")

                for index, box in enumerate(result.boxes):
                    cls = int(box.cls[0])
                    polygon = None
                    if result.masks is not None and index < len(result.masks.xy):
                        polygon = result.masks.xy[index].tolist()

                    detections.append({
                        "frame_number": frame_number,
                        "timestamp_seconds": round(timestamp, 2),
                        "damage_type": model.names[cls],
                        "confidence": round(float(box.conf[0]), 4),
                        "bbox_xyxy": [
                            round(float(value), 1)
                            for value in box.xyxy[0]
                        ],
                        "segmentation_polygon": polygon,
                        "defect_frame_path": str(frame_path),
                    })

            processed_sampled_frames += 1
            if on_progress is not None:
                    on_progress(
                        processed_sampled_frames,
                        total_sampled_frames,
                    )

        frame_number += 1

    capture.release()
    if on_progress is not None:
        on_progress(total_sampled_frames, total_sampled_frames)

    json_path = output_dir / "detections.json"
    report = {
        "video": str(video_path),
        "duration_seconds": round(duration, 2),
        "total_detections": len(detections),
        "detections": detections,
    }
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return {
        "duration_seconds": round(duration, 2),
        "json_path": str(json_path),
        "detections": detections,
    }
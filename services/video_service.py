from pathlib import Path


def analyze_video(video_path: Path, output_dir: Path, on_progress=None):
    from prediction import process_video

    return process_video(video_path, output_dir, on_progress=on_progress)

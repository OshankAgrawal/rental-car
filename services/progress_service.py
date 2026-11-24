from threading import Lock

_lock = Lock()
_progress_by_rental = {}


def set_progress(rental_id, stage, percent, detail):
    state = {
        "stage": stage,
        "percent": max(0, min(100, int(percent))),
        "detail": detail,
    }
    with _lock:
        _progress_by_rental[rental_id] = state


def get_progress(rental_id):
    with _lock:
        return _progress_by_rental.get(
            rental_id,
            {"stage": "waiting", "percent": 0, "detail": "Waiting for video upload"},
        ).copy()

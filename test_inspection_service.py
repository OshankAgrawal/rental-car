from types import SimpleNamespace
import unittest

from services.inspection_service import compare_damage, validate_video_upload


def detection(detection_id, name, box, confidence=0.8):
    return SimpleNamespace(
        id=detection_id,
        frame_number=detection_id,
        class_name=name,
        bbox_xyxy=box,
        confidence=confidence,
        defect_frame_path=f"frame-{detection_id}.jpg",
    )


class InspectionServiceTests(unittest.TestCase):
    def test_only_new_or_worsened_return_damage_requires_a_charge(self):
        pickup = [
            detection(1, "scratch", [0, 0, 20, 20]),
            detection(2, "dent", [30, 30, 50, 50]),
        ]
        returned = [
            detection(3, "scratch", [0, 0, 20, 20]),
            detection(4, "dent", [30, 30, 60, 60]),
            detection(5, "crack", [80, 80, 100, 100]),
        ]

        comparison = compare_damage(pickup, returned)

        self.assertEqual(
            [item["detection_id"] for item in comparison["charge_candidates"]],
            [4, 5],
        )
        self.assertEqual(
            comparison["charge_candidates"][0]["reason"],
            "potentially_worsened",
        )
        self.assertEqual(
            comparison["charge_candidates"][1]["reason"],
            "newly_detected",
        )
        self.assertEqual(
            [item["detection_id"] for item in comparison["existing"]],
            [3, 4],
        )

    def test_video_upload_rejects_unsupported_extensions(self):
        with self.assertRaisesRegex(ValueError, "Unsupported video format"):
            validate_video_upload(
                "inspection.txt",
                "video/mp4",
                {".mp4"},
                {"video/mp4"},
            )

    def test_repeated_video_frames_are_charged_as_one_damage_item(self):
        pickup = []
        returned = [
            detection(1, "scratch", [10, 10, 30, 30], confidence=0.7),
            detection(2, "scratch", [11, 10, 31, 30], confidence=0.9),
            detection(3, "scratch", [9, 10, 29, 30], confidence=0.8),
        ]

        candidates = compare_damage(pickup, returned)["charge_candidates"]

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["detection_id"], 2)
        self.assertEqual(len(candidates[0]["frames"]), 3)


if __name__ == "__main__":
    unittest.main()

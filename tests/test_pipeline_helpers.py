from __future__ import annotations

import unittest

from ppe_monitoring.video_id import resolve_video_id


class TestResolveVideoId(unittest.TestCase):
    def test_explicit_id(self):
        self.assertEqual(resolve_video_id("any", "  my_id  "), "my_id")

    def test_camera_index(self):
        self.assertEqual(resolve_video_id(3, None), "camera_3")
        self.assertEqual(resolve_video_id("0", None), "camera_0")

    def test_file_stem(self):
        self.assertEqual(resolve_video_id(r"C:\data\clip.mp4", None), "clip")

    def test_rtsp_host_path(self):
        vid = resolve_video_id("rtsp://user:pass@cam.local:554/live/stream1", None)
        self.assertTrue(vid.startswith("rtsp_"))
        self.assertIn("stream1", vid)


if __name__ == "__main__":
    unittest.main()

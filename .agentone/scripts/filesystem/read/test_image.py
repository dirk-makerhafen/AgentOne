import base64
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from image import read_image, MAX_EDGE_DEFAULT

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@unittest.skipUnless(PIL_AVAILABLE, "Pillow not installed")
class TestReadImage(unittest.TestCase):
    """Tests for the read_image tool."""

    def _make_image(self, size=(1200, 800), color=(200, 30, 30), fmt="JPEG") -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        Image.new("RGB", size, color).save(tmp.name, format=fmt)
        return tmp.name

    def test_read_image_returns_data_uri(self) -> None:
        path = self._make_image()
        try:
            success, result = read_image(path)
            self.assertTrue(success)
            self.assertEqual(result["content_type"], "image")
            self.assertTrue(result["image"].startswith("data:image/jpeg;base64,"))
            raw = base64.b64decode(result["image"].split(",", 1)[1])
            self.assertTrue(len(raw) > 1000)
            self.assertEqual(result["width"], 1200)
            self.assertEqual(result["height"], 800)
            self.assertEqual(result["format"], "JPEG")
        finally:
            os.unlink(path)

    def test_read_image_downscales(self) -> None:
        path = self._make_image(size=(4000, 3000))
        try:
            success, result = read_image(path, max_edge=1024)
            self.assertTrue(success)
            self.assertLessEqual(max(result["width"], result["height"]), 1024)
            img = Image.open(io.BytesIO(base64.b64decode(result["image"].split(",", 1)[1])))
            self.assertLessEqual(max(img.size), 1024)
        finally:
            os.unlink(path)

    def test_read_image_keeps_png_transparency(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        Image.new("RGBA", (640, 480), (10, 20, 30, 0)).save(tmp.name, format="PNG")
        try:
            success, result = read_image(tmp.name)
            self.assertTrue(success)
            self.assertTrue(result["image"].startswith("data:image/png;base64,"))
            self.assertEqual(result["format"], "PNG")
        finally:
            os.unlink(tmp.name)

    def test_read_image_missing_file(self) -> None:
        success, result = read_image("/nonexistent/nope.png")
        self.assertFalse(success)
        self.assertIn("not a file", result["message"].lower())

    def test_read_image_not_an_image(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"this is definitely not an image")
            f.flush()
            tmp_path = f.name
        try:
            success, result = read_image(tmp_path)
            self.assertFalse(success)
            self.assertEqual(result["status"], "error")
        finally:
            os.unlink(tmp_path)

    def test_read_image_no_path(self) -> None:
        success, result = read_image("")
        self.assertFalse(success)
        self.assertEqual(result["status"], "error")

    def test_read_image_default_max_edge(self) -> None:
        self.assertEqual(MAX_EDGE_DEFAULT, 2048)


if __name__ == "__main__":
    unittest.main()
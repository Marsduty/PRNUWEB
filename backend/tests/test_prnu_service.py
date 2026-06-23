from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from app.services.image_preprocess import load_rgb_square
from app.services import prnu_service
from app.services.prnu_service import DEFAULT_ENHANCEMENT_CONFIG, decide_database_matches, decide_external_match


def _png_bytes(size=(80, 64), color=(120, 130, 140)):
    image = Image.new("RGB", size, color)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _pattern_png_bytes(width=80, height=64):
    rows = np.arange(height, dtype=np.uint8)[:, None]
    cols = np.arange(width, dtype=np.uint8)[None, :]
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :, 0] = cols
    image[:, :, 1] = rows
    image[:, :, 2] = ((cols.astype(np.uint16) + rows.astype(np.uint16)) % 256).astype(np.uint8)
    buf = BytesIO()
    Image.fromarray(image, mode="RGB").save(buf, format="PNG")
    return buf.getvalue(), image


def test_load_rgb_square_returns_configured_shape():
    result = load_rgb_square(_png_bytes(), output_size=32)

    assert result.shape == (32, 32, 3)
    assert result.dtype == np.uint8


def test_load_rgb_square_center_crops_without_resizing():
    image_bytes, original = _pattern_png_bytes(width=80, height=64)

    result = load_rgb_square(image_bytes, output_size=32)

    expected = original[16:48, 24:56, :]
    assert np.array_equal(result, expected)


def test_load_rgb_square_rejects_images_smaller_than_output_size():
    with pytest.raises(ValueError, match="图像尺寸过小，最小边需要 >= 64px"):
        load_rgb_square(_png_bytes(size=(48, 80)), output_size=64)


def test_database_decision_uses_pce_threshold():
    rows = decide_database_matches(
        [{"name": "设备A", "pce": 61.0}, {"name": "设备B", "pce": 12.0}],
        threshold=60,
    )

    assert rows["decision"] == "倾向认定设备指纹：设备A 与待检图像同源"
    assert rows["hits"][0]["is_hit"] is True


def test_database_decision_reports_no_matching_device_when_below_threshold():
    rows = decide_database_matches(
        [{"name": "设备A", "pce": 59.9}, {"name": "设备B", "pce": 12.0}],
        threshold=60,
    )

    assert rows["decision"] == "库中未检索到匹配设备"
    assert rows["hits"] == []
    assert all(row["decision"] == "库中未检索到匹配设备" for row in rows["candidates"])


def test_external_decision_uses_pce_threshold():
    assert decide_external_match(61.0, threshold=60)["decision"] == "倾向认定图像 A 和图像 B 同源"
    assert decide_external_match(60.0, threshold=60)["decision"] == "倾向认定图像 A 和图像 B 不同源"


def test_external_comparison_includes_ncc_score():
    fingerprint = np.eye(8, dtype=np.float64)

    result = prnu_service.compare_external_images(fingerprint, fingerprint, threshold=60)

    assert "ncc" in result
    assert result["ncc"] > 0.99


def test_default_enhancement_config_uses_rsc_only():
    assert DEFAULT_ENHANCEMENT_CONFIG == (1, 0, 0, 0, 0)


def test_build_single_image_fingerprint_passes_default_enh_list(monkeypatch):
    captured = {}

    def fake_load_rgb_square(_image_bytes, output_size):
        assert output_size == 16
        return np.zeros((16, 16, 3), dtype=np.uint8)

    def fake_get_fingerprint(images, enh_list):
        captured["image_count"] = len(images)
        captured["enh_list"] = enh_list
        return np.zeros((16, 16), dtype=np.float64)

    monkeypatch.setattr(prnu_service, "load_rgb_square", fake_load_rgb_square)
    monkeypatch.setattr(prnu_service, "get_fingerprint", fake_get_fingerprint)

    prnu_service.build_single_image_fingerprint(b"fake-image", output_size=16)

    assert captured == {"image_count": 1, "enh_list": (1, 0, 0, 0, 0)}

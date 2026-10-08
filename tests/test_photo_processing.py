"""Tests for image parsing, EXIF extraction, and GPS conversion."""
import io
import pytest
from PIL import Image

import server


def test_read_photo_valid_sample_image(sample_image_path):
    data = sample_image_path.read_bytes()
    jpeg, taken, gps = server.read_photo(data)

    assert isinstance(jpeg, bytes)
    assert len(jpeg) > 0
    # Image must be valid JPEG decodable by PIL
    img = Image.open(io.BytesIO(jpeg))
    assert img.format == "JPEG"
    w, h = img.size
    assert w <= 1024 and h <= 1024


def test_read_photo_exif_timestamp_and_gps_extraction(demo_image_with_gps_path):
    data = demo_image_with_gps_path.read_bytes()
    jpeg, taken, gps = server.read_photo(data)

    assert taken == "2026-10-04T07:02:10"
    assert gps is not None
    lat, lon = gps
    assert round(lat, 4) == 21.1354
    assert round(lon, 4) == 79.0402


def test_read_photo_missing_exif(simple_jpeg_bytes):
    jpeg, taken, gps = server.read_photo(simple_jpeg_bytes)
    assert taken is None
    assert gps is None
    assert isinstance(jpeg, bytes)


def test_read_photo_malformed_bytes_raises_gracefully():
    with pytest.raises((ValueError, OSError)):
        server.read_photo(b"not an image at all, just junk data")


def test_read_photo_empty_bytes_raises_gracefully():
    with pytest.raises((ValueError, OSError)):
        server.read_photo(b"")


def test_read_photo_unusual_dimensions():
    # Very wide panorama
    wide_img = Image.new("RGB", (3200, 200), color=(100, 150, 200))
    buf = io.BytesIO()
    wide_img.save(buf, format="JPEG")

    jpeg, taken, gps = server.read_photo(buf.getvalue())
    img = Image.open(io.BytesIO(jpeg))
    w, h = img.size
    assert w <= 1024 and h <= 1024

    # Tiny 1x1 image
    tiny_img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    buf_tiny = io.BytesIO()
    tiny_img.save(buf_tiny, format="JPEG")
    jpeg_tiny, _, _ = server.read_photo(buf_tiny.getvalue())
    img_tiny = Image.open(io.BytesIO(jpeg_tiny))
    assert img_tiny.size == (1, 1)


def test_to_deg_north_and_east():
    # 40 deg 26 min 46 sec N
    deg = server._to_deg((40, 26, 46), "N")
    expected = 40 + 26 / 60 + 46 / 3600
    assert abs(deg - expected) < 1e-6
    assert deg > 0


def test_to_deg_south_and_west_are_negative():
    # 33 deg 51 min 54 sec S
    deg_s = server._to_deg((33, 51, 54), "S")
    assert deg_s < 0

    # 151 deg 12 min 36 sec W
    deg_w = server._to_deg((151, 12, 36), "W")
    assert deg_w < 0

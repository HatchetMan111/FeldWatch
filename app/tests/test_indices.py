import numpy as np
import pytest

from fieldwatch.indices import (
    NDVI_MAX,
    NDVI_MIN,
    clear_fraction,
    clear_mask,
    from_uint8_frame,
    ndvi_array,
    to_uint8_frame,
)


def test_ndvi_simple():
    red = np.array([[0.1, 0.2]], dtype=np.float32)
    nir = np.array([[0.5, 0.2]], dtype=np.float32)
    out = ndvi_array(red, nir)
    assert out[0, 0] == pytest.approx((0.5 - 0.1) / (0.5 + 0.1))
    assert out[0, 1] == pytest.approx(0.0)


def test_ndvi_zero_sum_is_nan_not_inf():
    red = np.array([[0.0]], dtype=np.float32)
    nir = np.array([[0.0]], dtype=np.float32)
    out = ndvi_array(red, nir)
    assert np.isnan(out[0, 0])
    assert not np.isinf(out[0, 0])


def test_ndvi_negative_sum_is_nan():
    out = ndvi_array(np.array([[-0.5]], dtype=np.float32), np.array([[0.2]], dtype=np.float32))
    assert np.isnan(out[0, 0])


def test_clear_mask_keeps_vegetation_and_bare_soil():
    scl = np.array([[4, 5, 7, 3, 8, 9, 10, 11, 0, 6]], dtype=np.uint8)
    mask = clear_mask(scl)
    assert mask.tolist() == [[True, True, True, False, False, False, False, False, False, False]]


def test_clear_fraction_ignores_outside():
    scl = np.array([[4, 4], [8, 8]], dtype=np.uint8)
    inside = np.array([[True, False], [True, False]])
    assert clear_fraction(clear_mask(scl), inside) == pytest.approx(0.5)


def test_clear_fraction_all_outside_is_zero():
    scl = np.array([[4]], dtype=np.uint8)
    inside = np.array([[False]])
    assert clear_fraction(clear_mask(scl), inside) == 0.0


def test_uint8_roundtrip():
    ndvi = np.array([[-0.2, 0.0, 0.5, 1.0]], dtype=np.float32)
    valid = np.array([[True, True, True, True]])
    frame = to_uint8_frame(ndvi, valid)
    assert frame.dtype == np.uint8
    back = from_uint8_frame(frame)
    np.testing.assert_allclose(back, ndvi, atol=(NDVI_MAX - NDVI_MIN) / 254 * 1.5)


def test_uint8_invalid_pixels_are_zero():
    ndvi = np.array([[0.5, np.nan]], dtype=np.float32)
    valid = np.array([[True, False]])
    frame = to_uint8_frame(ndvi, valid)
    assert frame[0, 1] == 0
    assert np.isnan(from_uint8_frame(frame)[0, 1])


def test_frame_is_downsampled_to_max_size():
    ndvi = np.full((600, 400), 0.5, dtype=np.float32)
    valid = np.ones((600, 400), dtype=bool)
    frame = to_uint8_frame(ndvi, valid, size=256)
    assert max(frame.shape) <= 256

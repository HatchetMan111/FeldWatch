from __future__ import annotations

import numpy as np

VALID_SCL = frozenset({4, 5, 7})
NDVI_MIN = -0.2
NDVI_MAX = 1.0
FRAME_SIZE = 256


def ndvi_array(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    red = red.astype(np.float32, copy=False)
    nir = nir.astype(np.float32, copy=False)
    denom = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / denom
    ndvi = np.where(denom > 0, ndvi, np.nan)
    ndvi = np.where(np.isfinite(ndvi), ndvi, np.nan)
    return np.clip(ndvi, -1.0, 1.0).astype(np.float32)


def clear_mask(scl: np.ndarray, valid: frozenset[int] = VALID_SCL) -> np.ndarray:
    return np.isin(scl, np.fromiter(valid, dtype=np.uint8))


def clear_fraction(mask: np.ndarray, inside: np.ndarray) -> float:
    total = int(inside.sum())
    if total == 0:
        return 0.0
    return float((mask & inside).sum()) / total


def _block_reduce(data: np.ndarray, factor: int, mask: np.ndarray | None) -> np.ndarray:
    if factor <= 1:
        return data
    h, w = data.shape
    ph = (-h) % factor
    pw = (-w) % factor
    if ph or pw:
        data = np.pad(data, ((0, ph), (0, pw)), mode="edge")
        if mask is not None:
            mask = np.pad(mask, ((0, ph), (0, pw)), mode="constant", constant_values=False)
    h, w = data.shape
    reshaped = data.reshape(h // factor, factor, w // factor, factor)
    with np.errstate(invalid="ignore"):
        if mask is None:
            return np.nanmean(reshaped, axis=(1, 3))
        masked = np.where(mask.reshape(h // factor, factor, w // factor, factor), reshaped, np.nan)
        return np.nanmean(masked, axis=(1, 3))


def to_uint8_frame(ndvi: np.ndarray, valid: np.ndarray, size: int = FRAME_SIZE) -> np.ndarray:
    data = np.where(valid & np.isfinite(ndvi), ndvi, np.nan).astype(np.float32)
    factor = max(1, int(np.ceil(max(data.shape) / size)))
    reduced = _block_reduce(data, factor, valid)
    scaled = (reduced - NDVI_MIN) / (NDVI_MAX - NDVI_MIN)
    scaled = np.clip(scaled * 254.0 + 1.0, 1.0, 255.0)
    return np.where(np.isfinite(reduced), scaled, 0.0).astype(np.uint8)


def from_uint8_frame(frame: np.ndarray) -> np.ndarray:
    frame = frame.astype(np.float32)
    ndvi = (frame - 1.0) / 254.0 * (NDVI_MAX - NDVI_MIN) + NDVI_MIN
    return np.where(frame > 0, ndvi, np.nan).astype(np.float32)

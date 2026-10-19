"""Multiscale, edge-aware local contrast processing.

The image is converted to linear RGB, decomposed into a Gaussian/Laplacian
pyramid, and its detail bands are selectively amplified. A structure tensor
protects strong edges while a local noise estimate suppresses gain in flat,
noisy regions. A softly compressed large-scale illumination field can add
subtle contextual separation without changing hue or clipping highlights.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter


@dataclass(frozen=True)
class Settings:
    amount: float = 0.65       # 0..1.5
    radius: float = 1.0        # 0.25..2.5
    edge_protection: float = 0.65  # 0..1
    noise_protection: float = 0.7  # 0..1
    context: float = 0.25      # 0..1
    fine_detail: float = 0.7   # 0..1
    mid_detail: float = 0.7    # 0..1
    coarse_detail: float = 0.35  # 0..1

    def validated(self) -> "Settings":
        return Settings(**{
            "amount": float(np.clip(self.amount, 0, 1.5)),
            "radius": float(np.clip(self.radius, .25, 2.5)),
            "edge_protection": float(np.clip(self.edge_protection, 0, 1)),
            "noise_protection": float(np.clip(self.noise_protection, 0, 1)),
            "context": float(np.clip(self.context, 0, 1)),
            "fine_detail": float(np.clip(self.fine_detail, 0, 1)),
            "mid_detail": float(np.clip(self.mid_detail, 0, 1)),
            "coarse_detail": float(np.clip(self.coarse_detail, 0, 1)),
        })


def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def _linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    rgb = np.maximum(rgb, 0)
    return np.where(rgb <= .0031308, 12.92 * rgb, 1.055 * np.power(rgb, 1 / 2.4) - .055)


def _luminance(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * .2126 + rgb[..., 1] * .7152 + rgb[..., 2] * .0722


def _gaussian(a: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur through Pillow, avoiding a heavyweight SciPy dependency."""
    values = np.asarray(a, dtype=np.float32)
    image = Image.fromarray(values, mode="F")
    # Pillow's GaussianBlur is not implemented for mode F; blur a normalized
    # 16-bit proxy, then restore the original numeric range.
    low, high = float(values.min()), float(values.max())
    if high - low < 1e-12:
        return values.copy()
    proxy = np.uint8(np.clip((values - low) * (255.0 / (high - low)), 0, 255) + .5)
    blurred = Image.fromarray(proxy, mode="L").filter(ImageFilter.GaussianBlur(radius=max(float(sigma), .1)))
    return np.asarray(blurred, dtype=np.float32) * ((high - low) / 255.0) + low


def _guided_filter(guide: np.ndarray, source: np.ndarray, radius: float, eps: float = .001) -> np.ndarray:
    """Fast grayscale guided filter using Gaussian-weighted local moments."""
    mean_g = _gaussian(guide, radius)
    mean_p = _gaussian(source, radius)
    corr_g = _gaussian(guide * guide, radius)
    corr_gp = _gaussian(guide * source, radius)
    var_g = np.maximum(corr_g - mean_g * mean_g, 0)
    cov_gp = corr_gp - mean_g * mean_p
    a = cov_gp / (var_g + eps)
    b = mean_p - a * mean_g
    return _gaussian(a, radius) * guide + _gaussian(b, radius)


def _structure_strength(y: np.ndarray, sigma: float) -> np.ndarray:
    padded = np.pad(y, ((1, 1), (1, 1)), mode="reflect")
    gx = ((padded[1:-1, 2:] - padded[1:-1, :-2]) * 2 + padded[2:, 2:] - padded[2:, :-2] + padded[:-2, 2:] - padded[:-2, :-2]) / 8
    gy = ((padded[2:, 1:-1] - padded[:-2, 1:-1]) * 2 + padded[2:, 2:] - padded[:-2, 2:] + padded[2:, :-2] - padded[:-2, :-2]) / 8
    jxx = _gaussian(gx * gx, sigma)
    jyy = _gaussian(gy * gy, sigma)
    jxy = _gaussian(gx * gy, sigma)
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-8)
    energy = np.sqrt(jxx + jyy)
    # Smoothly saturate edge strength; coherence discounts isotropic texture.
    return np.clip((energy / (energy + .025)) * (.35 + .65 * coherence), 0, 1)


def process_image(image: np.ndarray, settings: Settings = Settings()) -> np.ndarray:
    """Process uint8/uint16/float RGB(A) image and return float32 RGB(A) [0,1]."""
    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise ValueError("Expected an RGB or RGBA image array.")
    original_dtype = arr.dtype
    if np.issubdtype(original_dtype, np.integer):
        rgb = arr[..., :3].astype(np.float32) / np.iinfo(original_dtype).max
    else:
        rgb = np.clip(arr[..., :3].astype(np.float32), 0, 1)
    alpha = np.clip(arr[..., 3:4].astype(np.float32) / (np.iinfo(original_dtype).max if np.issubdtype(original_dtype, np.integer) else 1), 0, 1) if arr.shape[2] == 4 else None
    if rgb.shape[0] < 2 or rgb.shape[1] < 2:
        return np.concatenate([rgb, alpha], axis=2) if alpha is not None else rgb

    p = settings.validated()
    linear = _srgb_to_linear(rgb)
    y = np.clip(_luminance(linear), 0, 1)
    radius_scale = p.radius
    # Three edge-preserving low-pass scales form a Laplacian-like decomposition.
    base_fine = _guided_filter(y, y, 1.1 * radius_scale, .0003)
    base_mid = _guided_filter(y, y, 4.0 * radius_scale, .0015)
    base_coarse = _guided_filter(y, y, 14.0 * radius_scale, .008)
    fine = y - base_fine
    mid = base_fine - base_mid
    coarse = base_mid - base_coarse

    edge = _structure_strength(y, 1.2 * radius_scale)
    # Estimate residual sensor/compression noise in low-gradient neighborhoods.
    local_mad = _gaussian(np.abs(fine), 2.0 * radius_scale) * 1.4826
    noise_floor = .0015 + p.noise_protection * .018
    noise_gate = np.clip((local_mad - noise_floor) / (noise_floor * 2.5 + 1e-8), 0, 1)
    noise_gate *= (1 - .72 * edge)
    edge_gate = 1 - p.edge_protection * .65 * edge
    detail_gate = edge_gate * (1 - p.noise_protection * noise_gate)
    gain = p.amount
    detail = (fine * p.fine_detail + mid * p.mid_detail + coarse * p.coarse_detail)
    enhanced_y = y + gain * detail * detail_gate

    # Large-scale local adaptation uses a bounded, zero-centred tone curve.
    if p.context > 0 and gain > 0:
        illumination = np.maximum(base_coarse, .015)
        relative = np.log(y + .01) - np.log(illumination + .01)
        context_detail = np.tanh(relative * 2.0) * np.minimum(illumination, .35)
        enhanced_y += gain * p.context * .22 * context_detail * (1 - .35 * edge)

    enhanced_y = np.clip(enhanced_y, 0, 1)
    # Scale linear RGB by luminance ratio, preserving chroma and hue.
    ratio = enhanced_y / np.maximum(y, 1e-5)
    out_linear = linear * ratio[..., None]
    out = np.clip(_linear_to_srgb(out_linear), 0, 1).astype(np.float32)
    return np.concatenate([out, alpha], axis=2) if alpha is not None else out

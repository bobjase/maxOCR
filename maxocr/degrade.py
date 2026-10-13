"""R5/R6 degradation pipeline.

An Instance holds only uniform random draws (and the string it is paired with). Severity s
is applied at materialization time, so the same instance at different s shares its noise
(common random numbers across fonts, R8, and across severities). s = 1 reproduces the
Section 7 placeholder centre: blur sigma 1.2, JPEG quality 40, 1 px ink dilation.

Images are uint8, 0 = ink, 255 = paper.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from .render import render

N_DRAWS = 32


@dataclass(frozen=True)
class Instance:
    index: int
    text: str
    u: tuple[float, ...]   # N_DRAWS uniforms in [0, 1)
    seed: int              # for per-pixel noise fields

    @property
    def cropped(self) -> bool:  # R10b stratum
        return self.u[20] < 0.2


def make_instance(index: int, text: str, bank_seed: int) -> Instance:
    rng = np.random.default_rng([bank_seed, index])
    return Instance(index, text, tuple(float(x) for x in rng.random(N_DRAWS)), int(rng.integers(2**31)))


def _sym(u: float) -> float:
    return 2.0 * u - 1.0


def params(inst: Instance, s: float) -> dict:
    """Fully specified operator chain (R6) for this instance at severity s."""
    u = inst.u
    return {
        "origin_px": (u[0], u[1]),                       # fractional pen-origin jitter
        "size_jitter_pt": 0.5 * _sym(u[2]),
        "ink_spread_px": s * (0.5 + u[3]),               # mean 1 px at s=1; >0 dilate
        "ink_erode": u[4] < 0.25,                        # a quarter of instances thin instead
        "rotation_deg": float(np.clip(3.0 * s * _sym(u[5]), -3, 3)),
        "perspective": 0.02 * s * np.array([u[6], u[7], u[8], u[9]]),
        "blur_sigma": 1.2 * s * (0.8 + 0.4 * u[10]),
        "resample": None if u[11] < 0.5 else {
            "factor": 1.0 / (1.0 + 0.6 * s * u[12]),
            "interp": "nearest" if u[13] < 0.5 else "bilinear"},
        "illum_amp": 60.0 * s * u[14],                   # gray levels across the line
        "illum_angle": 2 * np.pi * u[15],
        "noise_std": 10.0 * s * u[16],
        "salt_pepper": 0.004 * s * u[17] if u[18] < 0.3 else 0.0,
        "jpeg_quality": int(np.clip(round(100 - 60 * s * (0.8 + 0.4 * u[19])), 5, 95)),
        "crop": None if not inst.cropped else {
            "side": ["top", "bottom", "left", "right"][int(u[21] * 4)],
            "frac": 0.2 * u[22]},
        "threshold": {
            "adaptive": u[23] < 0.3,
            "offset": 25.0 * s * _sym(u[24]),
            "block": 2 * int(5 + 6 * u[25]) + 1,
            "C": 2 + 8 * u[26]},
    }


def _ink_spread(img, px, erode):
    if px <= 0:
        return img
    k = np.ones((3, 3), np.uint8)
    op = cv2.dilate if erode else cv2.erode      # ink is dark: eroding paper grows ink
    out = img.astype(np.float32)
    whole = int(px)
    for _ in range(whole):
        out = op(out, k)
    frac = px - whole
    if frac > 0:
        out = (1 - frac) * out + frac * op(out, k)
    return out


def _warp(img, rot_deg, persp):
    h, w = img.shape
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    d = persp * np.array([w, h, w, h]) * np.array([1, 1, -1, -1])
    dst = src + np.float32([[d[0], d[1]], [-d[2], d[1]], [-d[2], -d[3]], [d[0], -d[3]]]) * 0.5
    M = cv2.getPerspectiveTransform(src, dst)
    R = np.vstack([cv2.getRotationMatrix2D((w / 2, h / 2), rot_deg, 1.0), [0, 0, 1]])
    return cv2.warpPerspective(img, (R @ M).astype(np.float32), (w, h),
                               flags=cv2.INTER_LINEAR, borderValue=255)


def _crop(img, side, frac):
    ink = np.argwhere(img < 128)
    if len(ink) == 0 or frac <= 0:
        return img
    (y0, x0), (y1, x1) = ink.min(0), ink.max(0)
    cut = int(round(frac * (y1 - y0 + 1)))
    if side == "top":
        return img[y0 + cut:]
    if side == "bottom":
        return img[:y1 + 1 - cut]
    if side == "left":
        return img[:, x0 + cut:]
    return img[:, :x1 + 1 - cut]


def degrade(font: str, inst: Instance, s: float, size_pt: float = 8.0, dpi: int = 200,
            binarize: bool = True, px_scale: float = 1.0) -> np.ndarray:
    """Render and degrade. binarize=True is suite (a), False is suite (b) (R10). px_scale: the damage's pixel
    sizes (ink spread, blur, adaptive-threshold block) are defined at 200 dpi; at 300 dpi pass 1.5 so the
    damage is physically the same, only captured sharper."""
    p = params(inst, s)
    p["ink_spread_px"] *= px_scale
    p["blur_sigma"] *= px_scale
    p["threshold"]["block"] = 2 * int(p["threshold"]["block"] * px_scale / 2) + 1
    rng = np.random.default_rng(inst.seed)
    img = render(font, inst.text, size_pt + p["size_jitter_pt"], dpi, origin_px=p["origin_px"])
    img = np.pad(img, 6, constant_values=255).astype(np.float32)  # room for warp/rotation

    img = _ink_spread(img, p["ink_spread_px"], p["ink_erode"])
    img = _warp(img, p["rotation_deg"], p["perspective"])
    if p["blur_sigma"] > 0:
        img = cv2.GaussianBlur(img, (0, 0), p["blur_sigma"])
    if p["resample"]:
        h, w = img.shape
        f = p["resample"]["factor"]
        interp = cv2.INTER_NEAREST if p["resample"]["interp"] == "nearest" else cv2.INTER_LINEAR
        small = cv2.resize(img, (max(1, round(w * f)), max(1, round(h * f))), interpolation=cv2.INTER_AREA)
        img = cv2.resize(small, (w, h), interpolation=interp)
    if p["illum_amp"] > 0:
        h, w = img.shape
        yy, xx = np.mgrid[0:h, 0:w]
        proj = (xx * np.cos(p["illum_angle"]) + yy * np.sin(p["illum_angle"]))
        proj = (proj - proj.min()) / max(np.ptp(proj), 1)
        img = img - p["illum_amp"] * proj
    if p["noise_std"] > 0:
        img = img + rng.normal(0, p["noise_std"], img.shape)
    if p["salt_pepper"] > 0:
        m = rng.random(img.shape)
        img[m < p["salt_pepper"] / 2] = 0
        img[m > 1 - p["salt_pepper"] / 2] = 255
    img = np.clip(np.round(img), 0, 255).astype(np.uint8)

    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, p["jpeg_quality"]])
    assert ok
    img = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)

    if p["crop"]:
        img = _crop(img, p["crop"]["side"], p["crop"]["frac"])
    if binarize:
        t = p["threshold"]
        if t["adaptive"]:
            img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, t["block"], t["C"])
        else:
            otsu, _ = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            _, img = cv2.threshold(img, float(np.clip(otsu + t["offset"], 1, 254)), 255, cv2.THRESH_BINARY)
    return img


def clean(font: str, text: str, size_pt: float = 8.0, dpi: int = 200, binarize: bool = True) -> np.ndarray:
    """R7a clean condition: integer pen origin, no jitter, no degradation. Suite (a) is plain Otsu."""
    img = np.pad(render(font, text, size_pt, dpi), 6, constant_values=255)
    if binarize:
        _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return img


def placeholder_chain(img: np.ndarray, severity: float = 1.0, binarize: bool = True) -> np.ndarray:
    """Fixed blur/JPEG/dilate chain on an already-rendered image. Used by the risky-check tests."""
    out = cv2.GaussianBlur(img, (0, 0), 1.2 * severity) if severity > 0 else img
    ok, enc = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, int(round(100 - 60 * severity))])
    out = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)
    px = int(round(severity))
    if px > 0:
        out = cv2.erode(out, np.ones((2 * px + 1, 2 * px + 1), np.uint8))
    if binarize:
        _, out = cv2.threshold(out, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return out

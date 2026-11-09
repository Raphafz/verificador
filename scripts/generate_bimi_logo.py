"""Gera logo.svg BIMI (vetor SVG Tiny PS) a partir de logos-rmsys/icon.png."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "logos-rmsys" / "icon.png"
TMP = ROOT / "static" / "well-known" / "bimi" / "icon-128.png"
OUT = ROOT / "static" / "well-known" / "bimi" / "logo.svg"

SIZE = 128
BG_RGB = (0, 32, 89)  # #002059
FG_RGB = (0, 191, 255)  # cyan do ícone


def _rgb_to_bgr(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = rgb
    return b, g, r


def _raster_for_trace() -> np.ndarray:
    icon = Image.open(ICON).convert("RGBA")
    icon.thumbnail((SIZE - 8, SIZE - 8), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (*BG_RGB, 255))
    x = (SIZE - icon.width) // 2
    y = (SIZE - icon.height) // 2
    canvas.paste(icon, (x, y), icon)
    TMP.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(TMP, optimize=True)
    return cv2.cvtColor(np.array(canvas.convert("RGB")), cv2.COLOR_RGB2BGR)


def _bgr_to_hex(bgr: tuple[int, int, int]) -> str:
    b, g, r = bgr
    return f"#{r:02x}{g:02x}{b:02x}"


def _foreground_mask(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # Ciano do logo RM (anti-alias incluído)
    lower = np.array([78, 60, 120], dtype=np.uint8)
    upper = np.array([105, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask


def _contour_to_path(contour: np.ndarray) -> str:
    pts = contour.reshape(-1, 2)
    if len(pts) < 3:
        return ""
    parts = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for x, y in pts[1:]:
        parts.append(f"L {x:.1f} {y:.1f}")
    parts.append("Z")
    return " ".join(parts)


def _compound_path(contours: list[np.ndarray]) -> str:
    parts = [_contour_to_path(c) for c in contours if cv2.contourArea(c) >= 2]
    return " ".join(p for p in parts if p)


def _vectorize_opencv(bgr: np.ndarray) -> str:
    mask = _foreground_mask(bgr)
    fg_pixels = bgr[mask > 0]
    fg_color = _rgb_to_bgr(FG_RGB)
    if len(fg_pixels) > 0:
        median = np.median(fg_pixels, axis=0)
        fg_color = (int(median[0]), int(median[1]), int(median[2]))

    paths: list[str] = [
        f'<rect width="{SIZE}" height="{SIZE}" fill="{_bgr_to_hex(_rgb_to_bgr(BG_RGB))}"/>',
    ]

    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)

    hier = hierarchy[0]
    used: set[int] = set()

    for i, contour in enumerate(contours):
        if i in used or cv2.contourArea(contour) < 2:
            continue
        parent = hier[i][3]
        if parent != -1:
            continue

        group = [cv2.approxPolyDP(contour, 0.35, True)]
        used.add(i)
        child = hier[i][2]
        while child != -1:
            if cv2.contourArea(contours[child]) >= 2:
                group.append(cv2.approxPolyDP(contours[child], 0.35, True))
            used.add(child)
            child = hier[child][0]

        d = _compound_path(group)
        if d:
            rule = ' fill-rule="evenodd"' if len(group) > 1 else ""
            paths.append(
                f'<path fill="{_bgr_to_hex(fg_color)}"{rule} d="{d}"/>'
            )

    body = "\n".join(paths)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.2" '
        f'baseProfile="tiny-ps" width="{SIZE}" height="{SIZE}" '
        f'viewBox="0 0 {SIZE} {SIZE}">\n'
        f"<title>RM Systems</title>\n"
        f"{body}\n"
        "</svg>\n"
    )


def main() -> None:
    bgr = _raster_for_trace()
    svg = _vectorize_opencv(bgr)
    OUT.write_text(svg, encoding="utf-8")
    size = OUT.stat().st_size
    has_raster = "<image" in svg.lower()
    path_count = svg.count("<path")
    print(f"PNG trace source: {TMP} ({TMP.stat().st_size} bytes)")
    print(f"SVG written: {OUT} ({size} bytes, {path_count} paths)")
    print(f"Vector only: {'yes' if not has_raster else 'NO — fix required'}")
    if path_count < 1:
        print("WARN: nenhum path de foreground — revisar segmentação.")
    if size > 32768:
        print("WARN: SVG > 32KB — alguns validadores BIMI podem rejeitar.")
    if has_raster or path_count < 1:
        sys.exit(1)


if __name__ == "__main__":
    main()

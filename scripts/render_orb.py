"""Render the Echo orb: a clear glass sphere with a swirling blue-violet core.

Every animated term is periodic in t in [0, 1), so frame N equals frame 0 and
the 4 s loop has no seam. Background is pure black: the page blends the layer
with `mix-blend-mode: screen` plus a radial mask, so no square ever shows.

usage: python scripts/render_orb.py frontend/public/orb [--frames 120] [--size 512]
"""

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

BLUE = np.array([47, 107, 255], np.float32) / 255      # #2F6BFF
VIOLET = np.array([90, 76, 245], np.float32) / 255     # #5A4CF5
DEEP_VIOLET = np.array([124, 72, 240], np.float32) / 255
CYAN = np.array([110, 200, 255], np.float32) / 255
ICE = np.array([220, 232, 255], np.float32) / 255


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def render(size: int, t: float) -> np.ndarray:
    lin = (np.arange(size, dtype=np.float32) + 0.5) / size * 2 - 1
    x, y = np.meshgrid(lin, lin)  # y grows downward (image space)
    r = np.sqrt(x * x + y * y)
    R = 0.58  # sphere radius in [-1, 1] space (84u orb in a 145u layer)
    rho = r / R
    inside = rho < 1.0
    nz = np.sqrt(np.clip(1 - rho * rho, 0, 1))  # sphere normal z
    nx, ny = x / R, y / R

    phase = 2 * np.pi * t
    pulse = 0.82 + 0.18 * (0.5 + 0.5 * np.sin(2 * phase))  # two pulses per loop

    img = np.zeros((size, size, 3), np.float32)

    # ---- core: refracted swirl (lens-warped coordinates) ----
    warp = 1.0 - 0.28 * nz  # glass magnifies the centre
    cx, cy = x * warp / R, y * warp / R
    cr = np.sqrt(cx * cx + cy * cy)
    theta = np.arctan2(cy, cx)
    swirl = theta + 2.6 * (1 - cr) + phase  # one full turn per loop
    n1 = np.sin(3 * swirl + 5.0 * cr)
    n2 = np.sin(5 * swirl - 7.0 * cr + 2 * phase)
    n3 = np.sin(2 * swirl + 9.0 * cr - phase)
    filaments = np.clip(0.5 + 0.30 * n1 + 0.15 * n2 + 0.12 * n3, 0, 1) ** 2.2
    core_mask = np.exp(-((cr / (0.62 * pulse)) ** 2))
    density = filaments * core_mask * smoothstep(0.0, 0.28, cr) + core_mask * 0.18 * (1 - smoothstep(0.0, 0.28, cr))
    mixv = 0.5 + 0.5 * np.sin(swirl * 2 + cr * 3)
    core_col = BLUE[None, None] * (1 - mixv[..., None]) + DEEP_VIOLET[None, None] * mixv[..., None]
    hot = np.exp(-((cr / (0.26 * pulse)) ** 2))  # bright heart
    img += core_col * density[..., None] * 1.35
    img += CYAN[None, None] * (hot * 0.55 * pulse)[..., None]
    img += ICE[None, None] * (hot ** 3 * 0.35)[..., None]

    # ---- glass body: faint tint + Fresnel rim, brighter where the top light falls ----
    fresnel = (1 - nz) ** 3
    top_light = np.clip(0.55 - 0.45 * ny, 0.15, 1.0)
    rim = fresnel * top_light
    img += (BLUE * 0.85 + VIOLET * 0.15)[None, None] * (rim * 1.25)[..., None]
    img += VIOLET[None, None] * (fresnel * np.clip(0.5 + 0.5 * nx, 0, 1) * 0.35)[..., None]
    img += BLUE[None, None] * (0.06 * nz)[..., None]

    # ---- specular highlights: crisp top window + soft refracted caustic below ----
    L = np.array([0.0, -0.78, 0.62], np.float32)
    L /= np.linalg.norm(L)
    H = L + np.array([0, 0, 1], np.float32)
    H /= np.linalg.norm(H)
    ndoth = np.clip(nx * H[0] + ny * H[1] + nz * H[2], 0, 1)
    spec = ndoth ** 140
    window = np.exp(-(((rho - 0.93) / 0.035) ** 2)) * smoothstep(0.1, -0.7, ny)  # thin top rim glint
    img += ICE[None, None] * (window * 0.45)[..., None]
    img += ICE[None, None] * (spec * 1.1)[..., None]
    arc = np.exp(-(((rho - 0.84) / 0.07) ** 2)) * smoothstep(0.25, 0.85, ny)  # curved caustic
    shimmer = 0.75 + 0.25 * np.sin(nx * 6 + phase)  # light sliding through the glass
    img += (CYAN * 0.6 + BLUE * 0.4)[None, None] * (arc * 0.45 * shimmer * pulse)[..., None]

    img *= inside[..., None]

    # ---- anti-aliased edge + outer glow (fades out well inside the CSS mask) ----
    edge = smoothstep(1.0, 0.985, rho)
    img *= edge[..., None]
    outside = np.clip(rho - 1, 0, None)
    halo = np.exp(-((outside / 0.06) ** 2)) * 0.30 + np.exp(-((outside / 0.22) ** 2)) * 0.10
    halo *= np.clip(0.6 - 0.4 * ny, 0.2, 1.0) * pulse
    img += (BLUE * 0.8 + VIOLET * 0.2)[None, None] * (halo * (1 - edge))[..., None]

    img = 1 - np.exp(-img * 1.15)  # soft tone-map so highlights never clip harshly
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--size", type=int, default=512)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    Image.fromarray(render(args.size, 0.0)).save(out / "orb-plate.webp", quality=90, method=6)

    raw = b"".join(render(args.size, i / args.frames).tobytes() for i in range(args.frames))
    common = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
              "-s", f"{args.size}x{args.size}", "-r", "30", "-i", "-", "-an"]
    subprocess.run(common + ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34", "-row-mt", "1",
                             "-deadline", "good", "-cpu-used", "2", "-pix_fmt", "yuv420p",
                             str(out / "orb-loop.webm")], input=raw, check=True)
    subprocess.run(common + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                             "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                             str(out / "orb-loop.mp4")], input=raw, check=True)
    for f in sorted(out.iterdir()):
        print(f"{f.name}: {f.stat().st_size / 1024:.0f} KB", file=sys.stderr)


if __name__ == "__main__":
    main()

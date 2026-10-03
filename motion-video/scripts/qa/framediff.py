"""Shared helper: tiny grayscale frames → per-frame diffs and true single-frame flashes (stdlib + ffmpeg)."""
import subprocess


def frames(video: str, w: int = 54, h: int = 96):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    n = w * h
    return [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]


def mad(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def analyse(video: str):
    """d[n] = mean |f_n − f_{n−1}|; flashes = n where f_n differs from both neighbours but f_{n−1} ≈ f_{n+1}."""
    f = frames(video)
    d = [0.0] + [mad(f[i], f[i - 1]) for i in range(1, len(f))]
    flashes = [i for i in range(1, len(f) - 1)
               if d[i] > 4 and d[i + 1] > 4 and mad(f[i + 1], f[i - 1]) < 0.25 * min(d[i], d[i + 1])]
    return d, flashes

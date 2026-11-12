"""Replace waiting and refusal cells while preserving the other sheet poses."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from export_transparent import read_png, write_png  # noqa: E402


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "transparent"
REGIONS = {
    "idle": (0, 0, 455, 650),
    "waiting": (800, 0, 1199, 650),
    "cant": (590, 650, 1080, 1312),
}


def bounds(pixels: bytearray, width: int, region: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = region
    occupied = [
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if pixels[(y * width + x) * 4 + 3] > 16
    ]
    return (
        min(x for x, _ in occupied),
        min(y for _, y in occupied),
        max(x for x, _ in occupied) + 1,
        max(y for _, y in occupied) + 1,
    )


def place_pose(
    sheet: bytearray,
    sheet_width: int,
    pose_path: Path,
    region: tuple[int, int, int, int],
    target_height: int,
    center_x: int,
    baseline: int,
) -> None:
    source_width, source_height, pose = read_png(pose_path)
    x0, y0, x1, y1 = bounds(pose, source_width, (0, 0, source_width, source_height))
    cropped = bytearray((x1 - x0) * (y1 - y0) * 4)
    for row in range(y1 - y0):
        start = ((y0 + row) * source_width + x0) * 4
        cropped[row * (x1 - x0) * 4 : (row + 1) * (x1 - x0) * 4] = pose[
            start : start + (x1 - x0) * 4
        ]
    with tempfile.TemporaryDirectory(prefix="psl-sheet-") as directory:
        crop_path = Path(directory) / "crop.png"
        resized_path = Path(directory) / "resized.png"
        write_png(crop_path, x1 - x0, y1 - y0, cropped)
        subprocess.run(
            ["sips", "-Z", str(target_height), str(crop_path), "--out", str(resized_path)],
            check=True,
            capture_output=True,
        )
        resized_width, resized_height, resized = read_png(resized_path)
    destination_x = center_x - resized_width // 2
    destination_y = baseline - resized_height
    left, top, right, bottom = region
    if destination_x < left or destination_x + resized_width > right:
        raise ValueError(f"Pose too wide for sheet cell: {pose_path}")
    if destination_y < top or destination_y + resized_height > bottom:
        raise ValueError(f"Pose too tall for sheet cell: {pose_path}")
    for row in range(resized_height):
        source = row * resized_width * 4
        destination = ((destination_y + row) * sheet_width + destination_x) * 4
        sheet[destination : destination + resized_width * 4] = resized[
            source : source + resized_width * 4
        ]


def build(name: str, department: str) -> None:
    width, height, sheet = read_png(SOURCE / f"{department}-poses.png")
    if (width, height) != (1199, 1312):
        raise ValueError("Unexpected reference sheet size")
    idle_bounds = bounds(sheet, width, REGIONS["idle"])
    scale_height = idle_bounds[3] - idle_bounds[1]
    original = {
        pose: bounds(sheet, width, REGIONS[pose]) for pose in ("waiting", "cant")
    }
    for pose in ("waiting", "cant"):
        left, top, right, bottom = REGIONS[pose]
        for y in range(top, bottom):
            start = (y * width + left) * 4
            sheet[start : start + (right - left) * 4] = b"\0" * ((right - left) * 4)
        x0, _, x1, y1 = original[pose]
        place_pose(
            sheet,
            width,
            ROOT / f"{name}-{pose}.png",
            REGIONS[pose],
            scale_height,
            (x0 + x1) // 2,
            y1,
        )
    write_png(ROOT / f"{name}-poses.png", width, height, sheet)
    print(f"{name}-poses.png: {width}x{height} RGBA")


if __name__ == "__main__":
    for name, department in (("tola", "pmo"), ("chidi", "finance"), ("zainab", "hr")):
        build(name, department)

"""Clean generated mascot cutouts and place them on a 1024x1536 canvas."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from collections import deque
from pathlib import Path

from export_transparent import read_png, write_png


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    width, height, pixels = read_png(args.source)
    count = width * height
    core = bytearray(count)
    center = (height // 2) * width + width // 2
    if pixels[4 * center + 3] < 128:
        center = next(
            i for i in range(count) if pixels[4 * i + 3] >= 128
        )
    queue: deque[int] = deque([center])
    core[center] = 1
    while queue:
        index = queue.popleft()
        x, y = index % width, index // width
        for neighbor in (
            index - 1 if x else -1,
            index + 1 if x + 1 < width else -1,
            index - width if y else -1,
            index + width if y + 1 < height else -1,
        ):
            if neighbor >= 0 and not core[neighbor] and pixels[4 * neighbor + 3] >= 128:
                core[neighbor] = 1
                queue.append(neighbor)
    for i in range(count):
        if core[i]:
            pixels[4 * i + 3] = 255
            continue
        x, y = i % width, i // width
        adjacent = (
            (x > 0 and core[i - 1])
            or (x + 1 < width and core[i + 1])
            or (y > 0 and core[i - width])
            or (y + 1 < height and core[i + width])
        )
        if not adjacent:
            pixels[4 * i + 3] = 0

    with tempfile.TemporaryDirectory(prefix="psl-pose-") as directory:
        clean = Path(directory) / "clean.png"
        resized = Path(directory) / "resized.png"
        write_png(clean, width, height, pixels)
        subprocess.run(
            ["sips", "-Z", "1460", str(clean), "--out", str(resized)],
            check=True,
            capture_output=True,
        )
        small_width, small_height, small = read_png(resized)

    occupied_x = [i % small_width for i in range(small_width * small_height) if small[4 * i + 3] > 8]
    occupied_y = [i // small_width for i in range(small_width * small_height) if small[4 * i + 3] > 8]
    left, right = min(occupied_x), max(occupied_x) + 1
    top, bottom = min(occupied_y), max(occupied_y) + 1
    if right - left > 1024 or bottom - top > 1460:
        raise ValueError("Resized figure does not fit requested canvas")
    output = bytearray(1024 * 1536 * 4)
    x_offset = (1024 - (right - left)) // 2 - left
    y_offset = 38 - top
    for y in range(top, bottom):
        dst_y = y + y_offset
        if not 0 <= dst_y < 1536:
            continue
        source_start = (y * small_width + left) * 4
        destination_start = (dst_y * 1024 + left + x_offset) * 4
        output[destination_start : destination_start + (right - left) * 4] = small[
            source_start : source_start + (right - left) * 4
        ]
    write_png(args.output, 1024, 1536, output)
    print(f"{args.output}: 1024x1536 RGBA")


if __name__ == "__main__":
    main()

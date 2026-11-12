"""Export the approved clay mascot renders with a transparent background.

The source renders use a nearly neutral off-white backdrop. Their characters
are deliberately monochrome, so chroma separates foreground from backdrop
without changing the approved character pixels.
"""

from __future__ import annotations

import argparse
import struct
import zlib
from collections import deque
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png(path: Path) -> tuple[int, int, bytearray]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"Not a PNG: {path}")
    offset = len(PNG_SIGNATURE)
    compressed = bytearray()
    width = height = channels = 0
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += length + 12
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
            if bit_depth != 8 or color_type not in (2, 6) or compression or filtering or interlace:
                raise ValueError(f"Unsupported PNG format: {path}")
            channels = 4 if color_type == 6 else 3
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
    raw = zlib.decompress(compressed)
    stride = width * channels
    pixels = bytearray(width * height * 4)
    previous = bytearray(stride)
    src = 0
    for y in range(height):
        filtering = raw[src]
        src += 1
        row = bytearray(raw[src : src + stride])
        src += stride
        for i in range(stride):
            left = row[i - channels] if i >= channels else 0
            above = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            if filtering == 1:
                row[i] = (row[i] + left) & 255
            elif filtering == 2:
                row[i] = (row[i] + above) & 255
            elif filtering == 3:
                row[i] = (row[i] + ((left + above) >> 1)) & 255
            elif filtering == 4:
                estimate = left + above - upper_left
                distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
                predictor = (left, above, upper_left)[distances.index(min(distances))]
                row[i] = (row[i] + predictor) & 255
            elif filtering != 0:
                raise ValueError(f"Unsupported PNG row filter: {filtering}")
        target = y * width * 4
        if channels == 4:
            pixels[target : target + width * 4] = row
        else:
            for x in range(width):
                pixels[target + 4 * x : target + 4 * x + 4] = row[3 * x : 3 * x + 3] + b"\xff"
        previous = row
    return width, height, pixels


def write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(
            ">I", zlib.crc32(kind + payload) & 0xFFFFFFFF
        )

    stride = width * 4
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(pixels[y * stride : (y + 1) * stride])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        PNG_SIGNATURE
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 6))
        + chunk(b"IEND", b"")
    )


def remove_neutral_background(width: int, height: int, pixels: bytearray) -> None:
    count = width * height
    chroma = bytearray(count)
    solid = bytearray(count)
    for i in range(count):
        p = i * 4
        red, green, blue = pixels[p], pixels[p + 1], pixels[p + 2]
        difference = max(red, green, blue) - min(red, green, blue)
        chroma[i] = min(difference, 255)
        solid[i] = difference >= 16

    # The eyes, badge and receipt can be neutral. Keep neutral islands that are
    # enclosed by the colored character rather than punching holes in them.
    outside = bytearray(count)
    queue: deque[int] = deque()
    for x in range(width):
        for index in (x, (height - 1) * width + x):
            if not solid[index] and not outside[index]:
                outside[index] = 1
                queue.append(index)
    for y in range(height):
        for index in (y * width, y * width + width - 1):
            if not solid[index] and not outside[index]:
                outside[index] = 1
                queue.append(index)
    while queue:
        index = queue.popleft()
        x, y = index % width, index // width
        for neighbor in (
            index - 1 if x else -1,
            index + 1 if x + 1 < width else -1,
            index - width if y else -1,
            index + width if y + 1 < height else -1,
        ):
            if neighbor >= 0 and not solid[neighbor] and not outside[neighbor]:
                outside[neighbor] = 1
                queue.append(neighbor)

    for i in range(count):
        if solid[i] or not outside[i]:
            alpha = 255
        else:
            # Retain just the antialias pixels immediately next to a figure.
            x, y = i % width, i // width
            touches_figure = (
                (x > 0 and solid[i - 1])
                or (x + 1 < width and solid[i + 1])
                or (y > 0 and solid[i - width])
                or (y + 1 < height and solid[i + width])
            )
            alpha = min(220, max(0, (chroma[i] - 3) * 20)) if touches_figure else 0
        pixels[4 * i + 3] = alpha


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    width, height, pixels = read_png(args.source)
    remove_neutral_background(width, height, pixels)
    write_png(args.output, width, height, pixels)
    print(f"{args.output}: {width}x{height} RGBA")


if __name__ == "__main__":
    main()

"""Cut the committed fixture crops (bloons/data/fixtures/*.png) out of the full frames in
bloons/data/fixtures_full/ (gitignored, Mac only), as listed in bloons/data/fixtures/crops.json.

    .venv/bin/python scripts/make_crops.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import Quartz as Q  # noqa: E402

from bloons.coords import box_to_pixels  # noqa: E402
from bloons.platform_mac import UI, load_png, png_bytes  # noqa: E402

FIX, FULL = ROOT / "bloons/data/fixtures", ROOT / "bloons/data/fixtures_full"


def main():
    spec = json.loads((FIX / "crops.json").read_text())["crops"]
    total = 0
    for name, c in spec.items():
        src = FULL / c["src"]
        if not src.exists():
            print(f"skip {name}: {src.name} missing")
            continue
        img = load_png(src)
        w, h = Q.CGImageGetWidth(img), Q.CGImageGetHeight(img)
        tb = round(UI["window"]["title_bar_pt"] * w / UI["window"]["expected_pt"][0])
        x, y, cw, ch = box_to_pixels(c["box"], w, h, tb)
        data = png_bytes(Q.CGImageCreateWithImageInRect(img, Q.CGRectMake(x, y, cw, ch)))
        (FIX / f"{name}.png").write_bytes(data)
        total += len(data)
        print(f"{name:30} {cw}x{ch} {len(data) / 1e3:7.0f} kB")
    print(f"total {total / 1e6:.2f} MB")


if __name__ == "__main__":
    main()

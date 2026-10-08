#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为某个角色的横版设定板生成「便于查看」的小尺寸 JPG。

原像素母版动辄上万像素、上亿像素总量，Windows 照片查看器会解码失败并
误报「文件不存在」。本脚本按分区实际内容范围裁切，长边压到 MAXW 以内，
确保任何看图器都能打开。

用法：
    python make_viewable.py <角色工程目录> [<角色工程目录> ...]

参数是角色工程目录，不是仓库根。产出写入该目录下的 06_便于查看/。
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
MAXW = 4000


def build(proj_dir: Path) -> dict:
    board_dir = proj_dir / "05_横版设定板"
    boards = sorted(board_dir.glob("*_原像素.png"))
    if not boards:
        return dict(project=proj_dir.name, status="skip", reason="没有 *_原像素.png")
    native = boards[0]
    base = native.stem.replace("_原像素", "")
    out = proj_dir / "06_便于查看"
    out.mkdir(exist_ok=True)
    for old in out.glob("*_查看用.jpg"):
        old.unlink()

    im = Image.open(native)
    W, H = im.size
    written = []

    # 整板总览
    mid = im.copy()
    mid.thumbnail((MAXW, MAXW), Image.Resampling.LANCZOS)
    mp = out / f"{base}_全板总览_查看用.jpg"
    mid.save(mp, quality=88, subsampling=0)
    written.append(dict(file=mp.name, size=list(mid.size), mb=round(mp.stat().st_size / 1048576, 2)))

    # 分区查看图：按该区素材实际占据的范围裁切
    idx_path = board_dir / "拼接布局与素材索引.json"
    if idx_path.is_file():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        secs = sorted(idx["sections"], key=lambda s: s["y"])
        ys = [s["y"] for s in secs] + [H]
        for i, s in enumerate(secs):
            top = max(0, ys[i] - 30)
            bot = min(H, ys[i + 1] - 30 if i + 1 < len(ys) else H)
            g = s["group"]
            ps = [p for p in idx["placements"] if p["group"] == g]
            if not ps:
                continue
            x0 = max(0, min(p["cell"][0] for p in ps) - 40)
            x1 = min(W, max(p["cell"][0] + p["cell"][2] for p in ps) + 40)
            strip = im.crop((x0, top, x1, bot))
            strip.thumbnail((MAXW, MAXW), Image.Resampling.LANCZOS)
            p = out / f"{base}_{g}_查看用.jpg"
            strip.save(p, quality=90, subsampling=0)
            written.append(dict(file=p.name, size=list(strip.size),
                                mb=round(p.stat().st_size / 1048576, 2)))
    im.close()
    return dict(project=proj_dir.name, status="ok", native=str(native),
                native_size=[W, H], files=written)


def main():
    ap = argparse.ArgumentParser(description="生成便于查看的小尺寸 JPG")
    ap.add_argument("projects", nargs="+", help="一个或多个角色工程目录")
    args = ap.parse_args()
    targets = []
    for raw in args.projects:
        p = Path(raw).resolve()
        if not p.is_dir():
            print(json.dumps({"project": raw, "status": "skip", "reason": "目录不存在"},
                             ensure_ascii=False))
            continue
        targets.append(p)
    results = [build(t) for t in targets]
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

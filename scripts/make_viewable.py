#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为某个角色的横版设定板生成「便于查看」的小尺寸 JPG。

原像素母版动辄上万像素、上亿像素总量，Windows 照片查看器会解码失败并
误报「文件不存在」。本脚本按分区实际内容范围裁切，长边压到 MAXW 以内，
确保任何看图器都能打开。

用法：
    python make_viewable.py "03_DeepSeek娘_鲸鱼娘_横版"
    python make_viewable.py --all          # 处理 _设定图成品 下所有角色工程
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

BASE = paths.deliverables_root()
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
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", help="角色工程目录名，例如 03_DeepSeek娘_鲸鱼娘_横版")
    ap.add_argument("--all", action="store_true", help="处理全部角色工程")
    args = ap.parse_args()
    if args.all:
        targets = [d for d in sorted(BASE.iterdir())
                   if d.is_dir() and d.name[:2].isdigit() and (d / "05_横版设定板").is_dir()]
    elif args.project:
        targets = [BASE / args.project]
    else:
        ap.error("需要 project 参数或 --all")
    results = [build(t) for t in targets]
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

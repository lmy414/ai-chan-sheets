#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为某个角色的横版设定板生成 1:1 原像素分区切片（不缩放、不重采样）。

06_便于查看 里的 JPG 是为了「能打开」而压到长边 4000 的缩略图；本脚本用同
一套裁切规则，但保留母版原始像素，产出可直接提交到仓库的原图切片：

    05_横版设定板/<...>_原像素.png  ──裁切──▶  07_原图切片/横版完整设定图_<group>_原图.png

裁切范围与 make_viewable.py 逐行一致（同一套 section y 边界与 placements
cell x 范围，含末尾 H 哨兵），只是去掉 thumbnail 调用：像素 1:1 复制。

用法：
    python make_native_slices.py <角色工程目录> [<角色工程目录> ...]

参数是角色工程目录（其下有 05_横版设定板/），不是仓库根；脚本不写死任何
绝对路径。产出写入各工程目录下的 07_原图切片/，每个分区一张 PNG（optimize=True）。
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

BOARD_SUBDIR = "05_横版设定板"
INDEX_NAME = "拼接布局与素材索引.json"
OUT_SUBDIR = "07_原图切片"
OUT_PREFIX = "横版完整设定图"
OUT_SUFFIX = "_原图.png"

# 与 make_viewable.py 内的魔法数字保持一致
SECTION_TOP_MARGIN = 30
CELL_X_MARGIN = 40


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_regions(idx: dict, W: int, H: int):
    """按 make_viewable.py 的规则产出 (group, box, error)。

    box = (x0, top, x1, bot)，均为母版像素坐标、右/下开区间。
    """
    secs = sorted(idx["sections"], key=lambda s: s["y"])
    ys = [s["y"] for s in secs] + [H]
    for i, s in enumerate(secs):
        top = max(0, ys[i] - SECTION_TOP_MARGIN)
        bot = min(H, ys[i + 1] - SECTION_TOP_MARGIN if i + 1 < len(ys) else H)
        g = s["group"]
        ps = [p for p in idx["placements"] if p["group"] == g]
        if not ps:
            yield g, None, "该分区在 placements 中没有素材，跳过"
            continue
        x0 = max(0, min(p["cell"][0] for p in ps) - CELL_X_MARGIN)
        x1 = min(W, max(p["cell"][0] + p["cell"][2] for p in ps) + CELL_X_MARGIN)
        if x1 <= x0 or bot <= top:
            yield g, None, f"裁切范围越界: box=({x0}, {top}, {x1}, {bot}) 母版={W}x{H}"
            continue
        yield g, (x0, top, x1, bot), None


def build(proj_dir: Path) -> dict:
    name = proj_dir.name
    board_dir = proj_dir / BOARD_SUBDIR
    boards = sorted(board_dir.glob("*_原像素.png"))
    if not boards:
        return dict(project=name, status="skip",
                    reason=f"{BOARD_SUBDIR}/ 下没有 *_原像素.png")
    native = boards[0]

    idx_path = board_dir / INDEX_NAME
    if not idx_path.is_file():
        return dict(project=name, status="skip", reason=f"没有 {INDEX_NAME}")
    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        sections, placements = idx["sections"], idx["placements"]
        if not isinstance(sections, list) or not isinstance(placements, list):
            raise TypeError("sections/placements 不是列表")
        for s in sections:
            if "group" not in s or "y" not in s:
                raise KeyError("section 缺 group/y")
        for p in placements:
            if "group" not in p or len(p["cell"]) < 3:
                raise KeyError("placement 缺 group/cell")
    except (KeyError, TypeError, ValueError) as exc:
        return dict(project=name, status="error",
                    reason=f"{INDEX_NAME} 结构异常: {exc!r}")

    out = proj_dir / OUT_SUBDIR
    out.mkdir(exist_ok=True)
    for old in out.glob(f"*{OUT_SUFFIX}"):
        old.unlink()

    files, errors = [], []
    im = Image.open(native)
    try:
        W, H = im.size
        for group, box, err in iter_regions(idx, W, H):
            if err:
                errors.append(dict(group=group, error=err))
                continue
            x0, top, x1, bot = box
            strip = im.crop(box)
            expect = (x1 - x0, bot - top)
            if strip.size != expect:
                errors.append(dict(group=group, error=f"裁切尺寸异常: {strip.size} != {expect}"))
                strip.close()
                continue
            path = out / f"{OUT_PREFIX}_{group}{OUT_SUFFIX}"
            strip.save(path, optimize=True)  # 不缩放、不重采样，仅 PNG 编码
            strip.close()
            size = list(Image.open(path).size)
            files.append(dict(
                group=group,
                file=path.name,
                crop=list(box),
                size=size,
                bytes=path.stat().st_size,
                mb=round(path.stat().st_size / 1048576, 2),
                sha256=sha256_of(path),
            ))
    finally:
        im.close()

    status = "ok" if files and not errors else ("partial" if files else "error")
    return dict(project=name, status=status, native=native.name,
                native_size=[W, H], out_dir=str(out), files=files,
                errors=errors)


def main():
    ap = argparse.ArgumentParser(description="生成 1:1 原像素分区切片")
    ap.add_argument("projects", nargs="+", help="一个或多个角色工程目录")
    args = ap.parse_args()
    results = []
    for raw in args.projects:
        p = Path(raw).resolve()
        if not p.is_dir():
            results.append(dict(project=raw, status="skip", reason="目录不存在"))
            continue
        results.append(build(p))
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    bad = [r["project"] for r in results if r["status"] != "ok"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

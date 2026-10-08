#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立核验横版设定板：不采信 compose_landscape.py 自己的断言，全部从磁盘重算。

核验项：
  1. 母版 PNG 实际尺寸与宽高比（是否真横版、是否落在 1.3:1 ~ 2.4:1）
  2. 每条 placement：素材原图（alpha 合成白底）与板上对应矩形逐字节比对
  3. placement 的 width/height 是否等于素材原始尺寸、scale 是否为 1.0
  4. 格子/素材之间是否有重叠、是否越出画布
  5. 素材 sha256 是否与记录一致、是否有重复

用法：
    python verify_board.py <角色工程目录> [<角色工程目录> ...]

参数是角色工程目录，不是仓库根。全部通过时退出码为 0，可直接接进 CI。
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def verify(proj_dir: Path) -> dict:
    board_dir = proj_dir / "05_横版设定板"
    boards = sorted(board_dir.glob("*_原像素.png"))
    idx_path = board_dir / "拼接布局与素材索引.json"
    if not boards or not idx_path.is_file():
        return dict(project=proj_dir.name, status="skip", reason="缺少母版或索引")
    native = boards[0]
    idx = json.loads(idx_path.read_text(encoding="utf-8"))

    with Image.open(native) as im:
        im.load()
        W, H = im.size
        board = im.convert("RGB")

    problems = []
    aspect = W / H
    if not W > H:
        problems.append(f"不是横版：{W}x{H}")
    if not (1.3 <= aspect <= 2.4):
        problems.append(f"宽高比 {aspect:.3f} 不在 1.3~2.4 区间")

    match = 0
    mismatch = []
    size_bad = []
    used = []
    for pl in idx["placements"]:
        asset_path = proj_dir / pl["file"]
        if not asset_path.is_file():
            mismatch.append((pl["id"], "素材文件缺失"))
            continue
        with Image.open(asset_path) as im:
            im.load()
            w, h = im.size
            rgba = im.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, "white")
            bg.alpha_composite(rgba)
            expect = bg.convert("RGB")
        if [w, h] != [pl["width"], pl["height"]] or [w, h] != list(expect.size):
            size_bad.append((pl["id"], f"素材实测 {w}x{h} != placement {pl['width']}x{pl['height']}"))
            continue
        if pl.get("scale") != 1.0:
            size_bad.append((pl["id"], f"scale={pl.get('scale')}"))
            continue
        x, y = pl["x"], pl["y"]
        if x < 0 or y < 0 or x + w > W or y + h > H:
            mismatch.append((pl["id"], f"越界 x={x} y={y} w={w} h={h}"))
            continue
        patch = board.crop((x, y, x + w, y + h))
        if patch.tobytes() == expect.tobytes():
            match += 1
        else:
            diff = sum(1 for a, b in zip(patch.tobytes(), expect.tobytes()) if a != b)
            mismatch.append((pl["id"], f"逐字节不一致，差异字节 {diff}"))
        used.append((x, y, w, h))

    # 重叠检查：素材矩形两两
    overlaps = []
    for i in range(len(used)):
        for j in range(i + 1, len(used)):
            if rects_overlap(used[i], used[j]):
                overlaps.append((used[i], used[j]))

    # 格子两两
    cells = [tuple(pl["cell"]) for pl in idx["placements"]]
    cell_overlaps = []
    for i in range(len(cells)):
        for j in range(i + 1, len(cells)):
            if rects_overlap(cells[i], cells[j]):
                cell_overlaps.append((cells[i], cells[j]))

    # sha256 与记录一致性 + 去重
    digests = []
    for tid in json.loads((proj_dir / "制作清单.json").read_text(encoding="utf-8"))["tasks"]:
        rec = json.loads((proj_dir / "00_生成记录" / (tid + ".json")).read_text(encoding="utf-8"))
        if rec.get("status") != "success":
            problems.append(f"记录未成功：{tid} -> {rec.get('status')}")
            continue
        p = proj_dir / rec["group"] / Path(rec["output"]).name
        d = hashlib.sha256(p.read_bytes()).hexdigest()
        if d != rec["output_sha256"]:
            problems.append(f"素材哈希与记录不符：{tid}")
        digests.append(d)
    dup = len(digests) - len(set(digests))

    if mismatch:
        problems.append(f"{len(mismatch)} 条逐字节比对不通过")
    if size_bad:
        problems.append(f"{len(size_bad)} 条尺寸/scale 异常")
    if overlaps:
        problems.append(f"素材矩形重叠 {len(overlaps)} 对")
    if cell_overlaps:
        problems.append(f"格子重叠 {len(cell_overlaps)} 对")
    if dup:
        problems.append(f"素材重复（sha256 相同）{dup} 个")

    return dict(
        project=proj_dir.name, status="pass" if not problems else "fail",
        native=native.name, native_size=[W, H], aspect_ratio=round(aspect, 4),
        placements=len(idx["placements"]), byte_match=match,
        byte_mismatch=mismatch[:10], size_issues=size_bad[:10],
        asset_overlaps=len(overlaps), cell_overlaps=len(cell_overlaps),
        duplicate_assets=dup, problems=problems,
    )


def main():
    ap = argparse.ArgumentParser(description="独立核验横版设定板")
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
    results = [verify(t) for t in targets]
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    return 0 if all(r.get("status") in ("pass", "skip") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

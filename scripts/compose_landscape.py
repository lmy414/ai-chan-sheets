#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用横版设定板拼接脚本，只依赖 Pillow。

用法：
    python compose_landscape.py <角色工程目录>

工程目录里需要有 制作清单.json、00_生成记录/<id>.json，以及各分区的素材目录。
产出写入该目录下的 05_横版设定板/：

  05_横版设定板/<native_name>      原像素 PNG
  05_横版设定板/<preview_name>     浏览预览 JPG（长边 <= 4200）
  05_横版设定板/拼接布局与素材索引.json

与常见竖版设定板的区别：画布为横版（宽 > 高），每个分区只占一行，
行内素材从左到右排开，不做换行。
"""
import hashlib
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if len(sys.argv) < 2:
    sys.exit("用法：python compose_landscape.py <角色工程目录>")

ROOT = Path(sys.argv[1]).resolve()
assert (ROOT / "制作清单.json").is_file(), f"目录里没有制作清单.json：{ROOT}"

OUT = ROOT / "05_横版设定板"
OUT.mkdir(exist_ok=True)
Image.MAX_IMAGE_PIXELS = None

FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
FONT_PATH = FONT_DIR / "msyh.ttc"
FONT_BOLD = FONT_DIR / "msyhbd.ttc"
assert FONT_PATH.is_file(), (
    f"缺少中文字体：{FONT_PATH}。设定板文字用微软雅黑，"
    "非 Windows 环境请自行改成系统里的中文字体路径。")


def font(size, bold=False):
    path = FONT_BOLD if (bold and FONT_BOLD.is_file()) else FONT_PATH
    return ImageFont.truetype(str(path), size)


def fit_font(draw, text, max_width, start, minimum=22, bold=False, step=2):
    """返回能在 max_width 内放下的最大字号；放不下时按 step 递减。"""
    size = start
    while size > minimum:
        f = font(size, bold=bold)
        if draw.textlength(text, font=f) <= max_width:
            return f
        size -= step
    return font(minimum, bold=bold)


manifest = json.loads((ROOT / "制作清单.json").read_text(encoding="utf-8"))
selections = manifest.get("selections", {})

assets = []
for task_id in manifest["tasks"]:
    selected = selections.get(task_id, task_id)
    rec = json.loads((ROOT / "00_生成记录" / (selected + ".json")).read_text(encoding="utf-8"))
    assert rec["status"] == "success", f"素材尚未完成：{selected}"
    path = (ROOT / rec["group"] / Path(rec["output"]).name).resolve()
    assert path.is_relative_to(ROOT) and path.is_file(), f"素材缺失：{path}"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == rec["output_sha256"], f"原图已变动：{path}"
    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        assert list(im.size) == rec["dimensions"], f"尺寸与记录不一致：{path}"
        size, mode = im.size, im.mode
    label = rec.get("label") or task_id.split("_", 2)[-1]
    assets.append(dict(id=task_id, selected_task=selected, label=label,
                       group=rec["group"], path=path.relative_to(ROOT).as_posix(),
                       dimensions=list(size), mode=mode, sha256=digest,
                       model_requested=rec["model"], quality_requested=rec["quality"],
                       size_requested=rec["size"], returned_model=rec.get("returned_model"),
                       returned_settings=rec.get("returned_settings"),
                       inferred_details=rec.get("inferred_details", False),
                       prompt_file=f"00_提示词/{selected}.json",
                       generation_record=f"00_生成记录/{selected}.json"))

assert len(assets) == len(manifest["tasks"]), "素材数量与清单不一致"
assert len({a["sha256"] for a in assets}) == len(assets), "存在重复素材（sha256 相同）"

# ---------------------------------------------------------------- 横版布局参数
MARGIN = 110
GAP_X = 56
GAP_Y = 56
PAD_X = 28
LABEL_H = 92
CELL_BOTTOM = 56
TITLE_H = 96
COL_BG = "#FAFAFD"
COL_LINE = "#E1E2EE"
INK = "#272840"
PURPLE = "#6767A9"
MUTED = "#666B7E"
ACCENT = manifest.get("accent", "#8E6FC0")

rows = []
for sec in manifest["sections"]:
    group_assets = [a for a in assets if a["group"] == sec["group"]]
    assert group_assets, f"分区没有素材：{sec['group']}"
    cell_w = max(a["dimensions"][0] for a in group_assets) + PAD_X * 2
    cell_h = max(a["dimensions"][1] for a in group_assets) + LABEL_H + CELL_BOTTOM
    row_w = len(group_assets) * cell_w + (len(group_assets) - 1) * GAP_X
    rows.append(dict(sec=sec, assets=group_assets, cell_w=cell_w, cell_h=cell_h,
                     row_w=row_w, count=len(group_assets)))

block_w = max(r["row_w"] for r in rows)
board_w = MARGIN * 2 + block_w
HEADER_H = 268
FOOTER_H = 132

cursor = HEADER_H
placements = []
section_layout = []
for r in rows:
    sec = r["sec"]
    section_layout.append(dict(group=sec["group"], title=sec["title"], note=sec.get("note", ""),
                               y=cursor, line_y=cursor + TITLE_H - 18,
                               row_width=r["row_w"], count=r["count"]))
    cursor += TITLE_H
    row_x0 = MARGIN + (block_w - r["row_w"]) // 2
    for i, asset in enumerate(r["assets"]):
        cell_x = row_x0 + i * (r["cell_w"] + GAP_X)
        cell_y = cursor
        w, h = asset["dimensions"]
        x = cell_x + PAD_X + (r["cell_w"] - PAD_X * 2 - w) // 2
        y = cell_y + LABEL_H + (r["cell_h"] - LABEL_H - CELL_BOTTOM - h) // 2
        placements.append(dict(id=asset["id"], file=asset["path"], group=asset["group"],
                               x=x, y=y, width=w, height=h, scale=1.0,
                               cell=[cell_x, cell_y, r["cell_w"], r["cell_h"]]))
    cursor += r["cell_h"] + GAP_Y

board_h = cursor - GAP_Y + FOOTER_H
assert board_w > board_h, f"未满足横版要求：{board_w} x {board_h}"

board = Image.new("RGB", (board_w, board_h), "white")
draw = ImageDraw.Draw(board)
draw.rectangle((0, 0, board_w, 16), fill=ACCENT)
info = f"横版 {board_w} × {board_h} px\n宽高比 {board_w / board_h:.2f} : 1"
info_font = fit_font(draw, max(info.split("\n"), key=len), int(board_w * 0.20), 44, minimum=26)
info_w = max(draw.textlength(line, font=info_font) for line in info.split("\n"))
head_right = board_w - MARGIN - info_w - 60
title_font = fit_font(draw, manifest["board_title"], head_right - MARGIN, 112,
                      minimum=48, bold=True)
draw.text((MARGIN, 62), manifest["board_title"], font=title_font, fill=INK)
subtitle_font = fit_font(draw, manifest["board_subtitle"], head_right - MARGIN, 48, minimum=24)
draw.text((MARGIN, 200), manifest["board_subtitle"], font=subtitle_font, fill=MUTED)
draw.multiline_text((board_w - MARGIN - info_w, 74), info, font=info_font, fill=MUTED,
                    spacing=12, align="right")

for s in section_layout:
    title_font = fit_font(draw, s["title"], int(board_w * 0.4), 68, minimum=40, bold=True)
    draw.text((MARGIN, s["y"]), s["title"], font=title_font, fill=PURPLE)
    if s["note"]:
        note_avail = board_w - MARGIN * 2 - int(board_w * 0.42)
        note_font = fit_font(draw, s["note"], note_avail, 40, minimum=24)
        note_w = draw.textlength(s["note"], font=note_font)
        draw.text((board_w - MARGIN - note_w, s["y"] + 24), s["note"],
                  font=note_font, fill=MUTED)
    draw.line((MARGIN, s["line_y"], board_w - MARGIN, s["line_y"]), fill=COL_LINE, width=4)

by_id = {a["id"]: a for a in assets}
verification = []
for place in placements:
    asset = by_id[place["id"]]
    cx, cy, cw, ch = place["cell"]
    draw.rounded_rectangle((cx, cy, cx + cw, cy + ch), radius=28,
                           fill=COL_BG, outline=COL_LINE, width=3)
    # 标签统一取任务名后缀，保证各行排版一致；记录里的补充说明放到底部小字。
    label = place["id"].split("_", 2)[-1]
    note = (asset.get("label") or "").strip()
    if note in ("", label):
        note = ""
    label_font = fit_font(draw, label, cw - PAD_X * 2, 50, minimum=22, bold=True)
    lw = draw.textlength(label, font=label_font)
    draw.text((cx + (cw - lw) / 2, cy + 22), label, font=label_font, fill=INK)
    with Image.open(ROOT / asset["path"]) as im:
        rgba = im.convert("RGBA")
        white = Image.new("RGBA", rgba.size, "white")
        white.alpha_composite(rgba)
        original_on_white = white.convert("RGB")
        board.paste(original_on_white, (place["x"], place["y"]))
        patch = board.crop((place["x"], place["y"],
                            place["x"] + place["width"], place["y"] + place["height"]))
        assert patch.tobytes() == original_on_white.tobytes(), f"像素校验失败：{asset['id']}"
    caption = f'{asset["dimensions"][0]} × {asset["dimensions"][1]} px · 独立原图 1:1'
    if note:
        caption = f"{note}　·　{caption}"
    cap_font = fit_font(draw, caption, cw - PAD_X * 2, 34, minimum=18)
    cap_w = draw.textlength(caption, font=cap_font)
    draw.text((cx + (cw - cap_w) / 2, cy + ch - CELL_BOTTOM + 8), caption,
              font=cap_font, fill=MUTED)
    verification.append(dict(id=asset["id"], pixel_match=True, scale=1.0,
                             x=place["x"], y=place["y"],
                             width=place["width"], height=place["height"]))

footnote = manifest["footnote"]
draw.text((MARGIN, board_h - 92), footnote,
          font=fit_font(draw, footnote, board_w - MARGIN * 2, 38, minimum=24), fill=MUTED)

native = OUT / manifest["native_name"]
board.save(native, optimize=False, compress_level=6)

preview = board.copy()
preview.thumbnail((4200, 4200), Image.Resampling.LANCZOS)
preview_path = OUT / manifest["preview_name"]
preview.save(preview_path, quality=92, subsampling=0)
assert preview.size[0] > preview.size[1], "预览图未保持横版"

with Image.open(native) as saved:
    assert saved.size == (board_w, board_h)
    saved.verify()

layout = dict(character=manifest["character"], orientation="landscape",
              board_dimensions=[board_w, board_h],
              board_aspect_ratio=round(board_w / board_h, 4),
              preview_dimensions=list(preview.size),
              native_file=native.name, preview_file=preview_path.name,
              original_scale=1.0, geometry_resized=False, geometry_cropped=False,
              alpha_compositing="原图透明像素合成白底，独立原图保持原文件",
              layout_mode="分区横向并排，每分区一行，行内从左到右",
              sections=[dict(group=s["group"], title=s["title"], note=s["note"],
                             y=s["y"], count=s["count"]) for s in section_layout],
              selections=selections, assets=assets, placements=placements,
              verification=verification)
(OUT / "拼接布局与素材索引.json").write_text(
    json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(dict(status="success", native=str(native), preview=str(preview_path),
                      dimensions=[board_w, board_h],
                      aspect_ratio=round(board_w / board_h, 3),
                      preview_dimensions=list(preview.size),
                      asset_count=len(assets), pixel_match_count=len(verification)),
                 ensure_ascii=False))

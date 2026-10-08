#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐项调用本机绘图工具生成一张素材；每次只执行一个任务。

用法：python scripts/render_asset.py <任务id>
"""
import hashlib
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
for name in ("OPENAI_BASE_URL", "OPENAI_API_KEY"):
    os.environ.pop(name, None)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402  （同目录下的路径解析模块）

GEN_PATH = paths.image_gen_tool()
assert GEN_PATH.is_file(), (
    f"缺少本机绘图工具：{GEN_PATH}；"
    "请在 scripts/workflow_config.json 里设置 image_gen_tool，"
    "或设置环境变量 AICHAN_IMAGE_GEN。")
spec = importlib.util.spec_from_file_location("local_image_gen", GEN_PATH)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

task_path = (ROOT / "00_提示词" / (sys.argv[1] + ".json")).resolve()
assert task_path.is_relative_to(ROOT) and task_path.is_file(), f"缺少提示词：{task_path}"
task = json.loads(task_path.read_text(encoding="utf-8"))

record_path = ROOT / "00_生成记录" / (task["id"] + ".json")
if record_path.exists():
    previous = json.loads(record_path.read_text(encoding="utf-8"))
    if previous.get("status") == "success":
        raise SystemExit("任务已完成；复用现有文件，修改请建立新版本任务。")
    history_dir = ROOT / "00_生成记录" / "历史记录"
    history_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    (history_dir / (task["id"] + "_" + stamp + ".json")).write_text(
        json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8")

cfg = gen.load_config()
assert cfg["base_url"] == "http://127.0.0.1:8317", "仅允许本机绘图接口"
cfg["timeout"] = 900
cfg["quality"] = gen.validate_quality(task["quality"])
model = gen.validate_model(task["model"])
output_dir = (ROOT / task["group"]).resolve()
assert output_dir.is_relative_to(ROOT)
output_dir.mkdir(parents=True, exist_ok=True)
cfg["output_dir"] = str(output_dir)


def resolve_reference(value):
    if value.startswith("@"):
        previous = json.loads((ROOT / "00_生成记录" / (value[1:] + ".json")).read_text(encoding="utf-8"))
        assert previous["status"] == "success", "前置参考图必须成功"
        return Path(previous["output"])
    return Path(value)


refs = [resolve_reference(p) for p in task["refs"]]
assert refs and all(p.is_file() for p in refs), "参考图必须存在"

record = dict(task, status="running", started_at=datetime.now(timezone.utc).isoformat(),
              endpoint="images/edits",
              reference_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in refs})
record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

start = time.monotonic()
try:
    response = gen.call_images_edits(cfg, task["prompt"], refs, model, task["size"], 1,
                                     quality=task["quality"])
    paths = gen.save_result(response, cfg, task["id"])
    assert len(paths) == 1, "每个任务必须只返回一张可保存的原图"
    with Image.open(paths[0]) as im:
        im.verify()
    with Image.open(paths[0]) as im:
        dimensions = list(im.size)
    record.update(status="success", output=str(paths[0]), dimensions=dimensions,
                  elapsed_seconds=round(time.monotonic() - start, 2),
                  usage=response.get("usage"), returned_model=response.get("model"),
                  returned_settings={k: response.get(k) for k in
                                     ("size", "quality", "background", "output_format")},
                  output_sha256=hashlib.sha256(paths[0].read_bytes()).hexdigest())
    print(json.dumps({k: record[k] for k in ("id", "status", "model", "quality", "output",
                                             "dimensions", "elapsed_seconds")},
                     ensure_ascii=False))
except Exception as exc:  # noqa: BLE001
    record.update(status="failed", error=str(exc),
                  elapsed_seconds=round(time.monotonic() - start, 2))
    print(json.dumps({"id": task["id"], "status": "failed", "error": str(exc)},
                     ensure_ascii=False))
    raise
finally:
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

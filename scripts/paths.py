#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径解析：让工作流脚本不依赖写死的绝对路径。

解析顺序：
  1. 环境变量 AICHAN_LIB_ROOT / AICHAN_IMAGE_GEN
  2. 本文件同目录下的 workflow_config.json
  3. 都没有时报错，并提示怎么配置

复制 workflow_config.example.json 为 workflow_config.json，按自己的机器填写。
workflow_config.json 已被 .gitignore 忽略，不会入库。
"""
import json
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
CONFIG_PATH = _HERE / "workflow_config.json"


def _load_config() -> dict:
    if CONFIG_PATH.is_file():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


CONFIG = _load_config()

HINT = ("请复制 scripts/workflow_config.example.json 为 scripts/workflow_config.json 并填写，"
        "或设置对应的环境变量。")


def _resolve(env_name: str, cfg_key: str, what: str) -> Path:
    value = os.environ.get(env_name) or CONFIG.get(cfg_key)
    if not value:
        raise RuntimeError(f"未配置{what}。{HINT}")
    return Path(value)


def library_root() -> Path:
    """角色参考图库根目录，内含 _设定图成品/。"""
    return _resolve("AICHAN_LIB_ROOT", "library_root", "角色参考图库根目录")


def deliverables_root() -> Path:
    """所有角色工程所在的目录。"""
    cfg = CONFIG.get("deliverables_root")
    return Path(cfg) if cfg else library_root() / "_设定图成品"


def image_gen_tool() -> Path:
    """本机绘图工具 gen.py 的路径，即 gpt-image-gen 技能的入口。"""
    return _resolve("AICHAN_IMAGE_GEN", "image_gen_tool", "本机绘图工具路径")


def font_path(bold: bool = False) -> Path:
    """设定板文字用的中文字体，默认取 Windows 的微软雅黑。"""
    cfg = CONFIG.get("font_bold" if bold else "font")
    if cfg:
        return Path(cfg)
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / name


if __name__ == "__main__":
    try:
        info = dict(library_root=str(library_root()),
                    deliverables_root=str(deliverables_root()),
                    image_gen_tool=str(image_gen_tool()),
                    image_gen_tool_exists=image_gen_tool().is_file(),
                    font=str(font_path()), font_exists=font_path().is_file())
    except RuntimeError as exc:
        info = dict(error=str(exc))
    print(json.dumps(info, ensure_ascii=False, indent=2))

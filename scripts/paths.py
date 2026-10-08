#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径解析：让工作流脚本不依赖任何写死的绝对路径。

解析顺序：
  1. 环境变量 AICHAN_LIB_ROOT
  2. 本文件同目录下的 workflow_config.json 里的 library_root
  3. 默认值（作者本机路径，仅作兜底）

复制 workflow_config.example.json 为 workflow_config.json 并按自己的机器改。
workflow_config.json 已在 .gitignore 中，不会入库。
"""
import json
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DEFAULT_LIB_ROOT = Path(r"E:\漫画工程\角色参考图库")
CONFIG_PATH = _HERE / "workflow_config.json"


def _load_config() -> dict:
    if CONFIG_PATH.is_file():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


CONFIG = _load_config()


def library_root() -> Path:
    """角色参考图库根目录（内含 _设定图成品/）。"""
    env = os.environ.get("AICHAN_LIB_ROOT")
    if env:
        return Path(env)
    cfg = CONFIG.get("library_root")
    if cfg:
        return Path(cfg)
    return DEFAULT_LIB_ROOT


def deliverables_root() -> Path:
    """所有角色工程所在的目录。"""
    cfg = CONFIG.get("deliverables_root")
    return Path(cfg) if cfg else library_root() / "_设定图成品"


def image_gen_tool() -> Path:
    """本机绘图工具 gen.py 的绝对路径（gpt-image-gen 技能入口）。

    默认按本机实际安装位置兜底；换机器请在 workflow_config.json 里指定
    image_gen_tool 字段。
    """
    env = os.environ.get("AICHAN_IMAGE_GEN")
    if env:
        return Path(env)
    cfg = CONFIG.get("image_gen_tool")
    if cfg:
        return Path(cfg)
    return Path(r"E:\M_Workbench\image-gen-tool\src\gen.py")


def font_path(bold: bool = False) -> Path:
    """中文字体路径（Windows 微软雅黑）。"""
    cfg = CONFIG.get("font_bold" if bold else "font")
    if cfg:
        return Path(cfg)
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / name


if __name__ == "__main__":
    print(json.dumps(dict(
        library_root=str(library_root()),
        deliverables_root=str(deliverables_root()),
        image_gen_tool=str(image_gen_tool()),
        image_gen_tool_exists=image_gen_tool().is_file(),
        font=str(font_path()),
        font_exists=font_path().is_file(),
    ), ensure_ascii=False, indent=2))

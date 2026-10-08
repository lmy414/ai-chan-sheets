# 工作流脚本

这套脚本是生成 `设定图/` 下所有成品的实际工具链，**按实际使用状态提供**，
只把写死的本机绝对路径改成可配置。

## 配置

```powershell
# 复制配置模板，按自己的机器改
Copy-Item scripts/workflow_config.example.json scripts/workflow_config.json
python scripts/paths.py        # 打印解析结果，确认路径都对
```

路径解析顺序：环境变量 → `workflow_config.json` → 内置默认值。

| 变量 / 配置项 | 用途 |
|---|---|
| `AICHAN_LIB_ROOT` / `library_root` | 角色参考图库根目录（内含 `_设定图成品/`） |
| `AICHAN_IMAGE_GEN` / `image_gen_tool` | 本机绘图工具 `gen.py` 的路径（gpt-image-gen 技能入口） |
| `font` / `font_bold` | 设定板文字用的中文字体 |

`workflow_config.json` 已被 `.gitignore` 忽略，不会入库。

## 目录约定

脚本假定每个角色工程是这样的结构，`compose_landscape.py` 与 `verify_board.py` 都按此定位：

```
<库根>/_设定图成品/<角色>_横版/
├── 制作清单.json          ← 含 character / tasks / sections / 成品命名 / accent
├── 00_提示词/<id>.json     ← 每条素材的提示词与生成参数
├── 00_生成记录/<id>.json   ← 每条素材的模型、质量、尺寸、sha256、输出路径
├── 01_三视图/ 02_表情/ 03_服装/ 04_道具细节/
├── 05_横版设定板/          ← 成品：原像素 PNG、浏览预览 JPG、拼接索引 JSON
└── 06_便于查看/            ← 长边 ≤4000px 的查看用 JPG
```

## 脚本一览

| 脚本 | 作用 |
|---|---|
| `paths.py` | 路径解析，被其余脚本导入 |
| `render_asset.py` | 执行**单条**任务：读提示词 → 调本机绘图 → 落图 → 写生成记录。已完成的任务会拒绝重跑 |
| `run_queue.ps1` | 按给定的 id 列表**串行**跑一批任务 |
| `run_retry.ps1` | **补齐所有未成功的任务**，带指数退避，可反复跑到全绿（推荐用这个） |
| `compose_landscape.py` | 拼**横版**设定板：分区横向并排、每分区一行、原生像素 1:1 粘贴，含逐字节自检 |
| `verify_board.py` | **独立核验**成品板：不采信拼接脚本自述，从磁盘重算逐字节比对、重叠、越界、尺寸 |
| `make_viewable.py` | 生成长边 ≤4000px 的总览与分区查看图（母版太大，看图器打不开） |
| `make_prompts.example.py` | 某个已完工角色的完整**提示词生成脚本**示例，可照此改写 |

## 典型用法

```powershell
# 1) 先跑一遍，失败的会留在记录里
.\scripts\run_retry.ps1 -Log .\00_生成记录\_worker日志\workerR.log -MaxAttempts 5 -BaseSleep 30

# 2) 全绿之后拼接
python scripts\compose_landscape.py

# 3) 独立核验（这一步才是"验收"，不要用拼接脚本的返回值当验收）
python scripts\verify_board.py --all

# 4) 出便于查看的小图
python scripts\make_viewable.py --all
```

`verify_board.py` 全部通过时退出码为 0，任一角色不通过为 1，可直接接进 CI。

## 两个硬约束

1. **像素保真**：`compose_landscape.py` 只做 1:1 粘贴，`scale` 恒为 1.0，不缩放不裁切；
   粘贴后原地裁剪回来逐字节自检，不一致直接断言失败。
2. **画布必须横版**：`board_w > board_h`，否则断言报错。
   这是本套流程与常见竖版设定板的关键区别。

## 注意

- **并发要压住**。本机绘图接口并发到 3–4 个请求就会触发上游缓冲超限
  （`507 exceeded request buffer limit` / `503 auth_unavailable`）。单进程串行最稳，
  失败交给 `run_retry.ps1` 退避重跑。
- **密钥不要写进提示词、不要提交**。脚本在启动时会清掉进程内的
  `OPENAI_BASE_URL` / `OPENAI_API_KEY`，避免覆盖本机配置。
- 素材是 RGBA 且 alpha 为柔性遮罩。自己写审图脚本时记得**先合成白底再转 RGB**，
  否则透明区会显示成黑底并产生噪点。
- 更多踩坑记录见 [`../docs/生图流程.md`](../docs/生图流程.md)。

# ArchAtlas Demo

一个模块级开源模型架构图谱原型：用可搜索的模型目录、结构流和模块字典，比较模型的架构模块。前端为原生 HTML/CSS/JavaScript，后端为 Python 标准库 HTTP Server，无需 Node/npm 或第三方 Python 包。

## 启动

```bash
python3 backend/server.py
```

然后打开 <http://127.0.0.1:8000>。可指定监听地址和端口：

```bash
python3 backend/server.py --host 0.0.0.0 --port 8080
```

## 当前模型快照

数据快照日期：**2026-10-01**。模型目录共有 **1,312 条记录**：

- **20 条已整理架构**：人工核验过的基础模型和近期架构代表模型，可展示模块结构流。
- **1,292 条待人工确认候选**：从 Hugging Face Hub API 按 **68 个配置的官方发布者/研究机构命名空间分页抓取**，覆盖 2025-01-01 以来符合 `text-generation` 与名称筛选规则的公开仓库；候选会与人工整理模型去重。
- 本快照共扫描 **3,393 个仓库**，筛出 1,304 个符合条件的候选仓库，扣除与已整理记录重复项后保留 1,292 条待人工确认记录。
- 已批量读取到 **1,211 份 config.json**，其中 **1,205 条候选**出现至少一项可追溯的结构线索（如 GQA 头数关系、专家数量/top-k、RoPE/RMSNorm 参数、滑窗/MTP 字段、模型类型映射）。另有 63 个仓库返回受限访问（401）、18 个没有可用 config.json。

> 这里的“全部”是指配置命名空间范围内符合 API、日期和名称规则的仓库，不是 Hugging Face 全站所有用户/组织，也不覆盖其他模型平台。候选不是架构结论：其中可能有研究实验、检查点或模型变体。配置线索和模型卡摘录都不等于人工核验；自动提取只帮助定位证据，不计入已核验模块统计。量化/格式转换与常见衍生仓库按名称规则过滤，因此也可能漏掉命名不明显的衍生项。

近期已整理代表模型包括：

- DeepSeek-V4-Pro、DeepSeek-V4-Flash、Xing4.0-29B-A4B
- Qwen3.8-2.4T-A95B、Qwen3-Coder-Next、GLM-5.3
- MiMo-V2.6-Pro-RL、MiMo-V2.6-Flash-RL、IQuest-Q1、AliceAI-Foundation-80B-A3B-Base
- NVIDIA Nemotron-3.5-Lightning-30B-A3B、Meituan LongCat-2.0、MiniCPM5-2B、IBM Granite-4.2-8B、LiquidAI LFM2.5-8B-A1B

重点模块包括 Gated DeltaNet、Gated Attention、KDA、Mamba-2、CSA/HCA、LongCat Sparse Attention、Double-Gated Convolution、DSA 与 MTP。

### 热门度排序

模型目录默认按“热门优先”排列。候选仓库的热度分数，是它在 Hugging Face trending、下载、点赞、创建时间、更新时间五种 top-1,000 榜单中出现过的名次归一化均分；榜单外候选仍保留，并以下载量、点赞量等快照信号作为后续排序依据。可切换到“最新优先”。这是本次抓取快照内的相对排序，不是跨平台或实时热度。

### 数据质量与边界

- 来源优先级为官方模型卡、`config.json`、技术报告和作者实现仓库。整理记录会保存来源链接与证据说明。
- 候选数据保存在 `data/discovered_models.json`，抓取范围与命名空间明细保存在 `data/discovery_metadata.json`；更新和证据采集脚本包括 `scripts/sync_hf_catalog.py`、`scripts/enrich_architecture.py`、`scripts/enrich_model_cards.py`。
- 候选结构初筛来自 Hugging Face 的 config.json：直接配置字段（如头数、专家数、top-k、层数）与模型类型家族推断会分开展示。另为 **100 个代表架构类型**抓取模型卡关键词上下文，其中 94 份成功、6 份受限（401）；摘录保留原文和来源链接，不会自动转成模块结论。目前已对其中 **7 个代表模型**逐条解读卡片里的架构陈述（见 `data/model_card_interpretations.json`），并在界面并列展示原文、模块映射与限制；这些仍是模型卡级证据，未完成代码/论文交叉核验，所以对应候选继续保持 pending，不计入已确认模块统计。其他候选、自定义模块、完整层序与残差/归一化细节仍需继续复核。未公开字段显示“未公开”，不会根据模型规模猜测。
- 模型卡仓库创建时间不一定等于正式发布日期；候选列表采用创建时间筛选，架构整理条目的 release 则基于官方发布信息。
- 已整理架构图是模块级概览，不是 PyTorch FX 图、逐算子计算图或 GPU kernel 图；没有下载完整权重，也不会尝试从权重自动反推结构。
- mHC 当前有 DeepSeek-V4 系列与 Xing4.0 的官方模型卡证据；Hy4-preview 模型卡也提到 iHC，但目前只保留在待核验候选的证据解读中，尚未并入已核验模块统计。

### 更新候选清单

联网运行脚本可从 Hugging Face API 重新抓取一份当前快照（会覆盖 `data/discovered_models.json` 和 `data/discovery_metadata.json`）：

```bash
python3 scripts/sync_hf_catalog.py
```

每次刷新都是一个新的时点样本，榜单名次、下载量和候选数量可能变化；并不表示模型架构已完成拆解。


### GitHub Pages 静态部署

ArchAtlas 前端原本依赖本地 Python API。`scripts/build_pages.py` 可将 API 快照预先导出为静态 JSON，从而部署到 GitHub Pages；构建输出适用于项目子路径（例如 `https://jaykay233.github.io/archatlas/`），不要求 Pages 运行后端服务。

当前 `jaykay233.github.io` 仓库已有个人网站，因此部署应新增 `/archatlas/` 子目录，不覆盖原首页。仓库的 Actions 工作流会每日抓取并重建静态快照；如果使用 Pages 的 Actions 部署模式，部署 artifact 需要包含现有网站根目录和 ArchAtlas 子目录。

本地生成预览：

```bash
python3 scripts/build_pages.py --output /tmp/archatlas-pages
```

### 每日自动更新（macOS）

本地 demo 可用 macOS `launchd` 每天自动刷新 Hugging Face 候选。任务按本机时间每天 **08:30** 运行：先更新候选仓库、榜单热度和下载/点赞快照，再只为新发现且尚未缓存的仓库读取 `config.json`。后端每次请求都会重新读取这些 JSON 文件，因此更新成功后重新加载页面即可看到新快照。

```bash
./scripts/install_daily_refresh.sh
# 需要时可手动立即跑一轮
python3 scripts/daily_refresh.py
# 查看运行日志
tail -f ~/Library/Logs/ArchAtlas/daily-refresh.log
# 取消每天的任务（保留日志和数据）
./scripts/uninstall_daily_refresh.sh
```

电脑关机或睡眠时任务不会在云端执行；唤醒后 `launchd` 会补跑错过的计划任务。自动更新仅采集公开元数据与配置证据，不下载权重，也不会把配置/模型卡候选自动升级为“已核验”架构。

仓库另提供 `.github/workflows/daily-hf-refresh.yml`：GitHub Actions 每天 **00:30 UTC（约 08:30 北京时间）**运行同一流水线、执行测试，并把有变化的数据快照提交回默认分支。也可在 GitHub 的 Actions 页面手动运行。它更新的是 GitHub 上的仓库，不会自动改写本地 Mac 工作区；若要更新线上网站，还需要配置部署流程。目前本地项目尚未设置 GitHub remote，需先创建/关联 GitHub 仓库并推送到默认分支，Actions 的定时任务才会真正启动。GitHub Actions 的 schedule 可能因平台负载有所延迟。

## Demo 功能

- 模型目录默认按热门度排序，也可按发布日期排序；可按模型、组织、架构特征搜索，支持待拆解 / Dense / MoE / GQA / MLA / mHC / iHC 筛选。待拆解条目单独显示仓库和配置元数据。
- 架构详情显示参数规模、层数、模块结构流、混合层布局与证据来源。
- 模块字典逐项列出已核验模型与带配置/模型卡线索的候选模型，支持按模型名筛选；点击模型名可跳转到该模型详情，并明确区分核验状态。
- 数据来源视图描述榜单发现、配置抽取、证据整理和人工复核的工作流。

## API

- `GET /api/health`
- `GET /api/stats`（含已整理 / 待拆解数量、静态快照日期与样本范围）
- `GET /api/models?q=mla&module=mla&family=DeepSeek`
- `GET /api/models/{model_id}`
- `GET /api/modules?q=attention&category=Attention`
- `GET /api/modules/{module_id}`（同时返回关联模型）

## 测试

```bash
python3 -m unittest discover -s tests -v
```

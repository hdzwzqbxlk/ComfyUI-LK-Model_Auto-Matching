# 网络模型匹配 · 轻量化可行性计划（深度调研）

> 调研日期：2026-08-13 · 路由：agent-reach（Exa 语义搜索 + GitHub/`gh` + WebSearch + Web 阅读）
> 目标：把插件的"全网搜索兜底"从「重、泛、易碎」改为「轻量、镜像优先、命中率高」。

---

## 0. TL;DR

插件当前兜底逻辑是并发搜 Civitai / HuggingFace / ModelScope / Liblib / Google / DuckDuckGo——**泛网页搜索重且精度低、易碎**（依赖搜索引擎反爬、无结构化结果）。

调研结论：**轻量化 = 「已知注册表 + 确定性镜像 URL + Civitai API 解析」三段式**。`Comfy-Org/*` 官方模型只是能用 hf-mirror 确定性直链覆盖的一块；真实工作流里大量缺失模型是 **Civitai / 社区 LoRA / 自定义 checkpoint 等非官方模型**，它们没有确定 HF 路径，必须靠 API 解析——其中 **`/model-versions/by-hash/{SHA256}` 按哈希精确解析**是轻量且高精度的"精准匹配"正解。这条路径已被 ComfyUI-Manager、Comfy-Org 官方管线、ComfyUI-Lora-Manager（Civitai 集成）、ComfyUI-ModelFinder 验证。本项目已有 `data/samples/`（kijai / comfy_gguf 源数据）→ 可作注册表种子，改造成本低。

**可行性：高。** 主要工作量 = 策展注册表（官方 + 热门 Civitai）+ 接入镜像端点 + 接入 Civitai API（by-hash 精确 + by-name 搜索）替换泛网页搜索。

---

## 1. 类同项目调研（8 个 + 官方管线）

| 项目 | 匹配/下载机制 | 是否实时搜网 | 轻量性 | 与本项目相关性 |
|------|--------------|------------|--------|--------------|
| **Comfy-Org 官方 missingModelPipeline** | 依赖 node 定义内嵌的已知 `url`+`directory`（作者预埋元数据），不搜网 | 否 | 最高 | 证明"已知 URL"路线可行 |
| **ComfyUI-Manager** | `node_db/model-list.json` 策展目录 + `manager_downloader.py`（aria2 多线程/续传/校验）；支持 `HF_ENDPOINT`/`GITHUB_ENDPOINT` 镜像 | 否（目录） | 高 | **最贴切参照**：注册表 + 镜像端点 |
| **comfyui-modelsearchandload** (tyl0re) | 扫工作流 → 从 HF/CivitAI 下载到正确目录；硬链接去重 | 否（直链） | 高 | 智能落盘路由参考 |
| **ComfyUI-ModelFinder** (xmy567) | **DrissionPage 无头浏览器 + Bing 搜索**，中文优先 Liblib、英文优先 HF，生成镜像链接；含"不规则名称映射表" | **是（浏览器）** | **重（依赖 Chrome）** | 国内方案思路可取，**形态要规避** |
| **ComfyUI-Lora-Manager** (willmiao) | **Civitai API 集成**：CivitaiClient 单例 + 元数据 provider 链（Civitai API → Archive DB → CivArchive 镜像）；**by-hash 精确解析** + base model 过滤 + 下载鉴权 | 是（API） | 高 | **社区模型路径最贴切参照**：by-hash/by-name + 镜像兜底 |
| ComfyUI-Workflow-Models-Downloader | 工作流缺失模型下载 | 部分 | 中 | 参考 |
| Comfyui-Model-Resolver (Azornes) | 模型解析/定位 | — | 中 | 参考 |
| ComfyUI-Model-Installer (arleckk) | 模型安装器 | — | 中 | 参考 |
| ComfyUI-ModelFrisk / AutoModelDownloader | 缺失模型扫描下载 | — | 中 | 参考 |

**关键取舍**：真正"轻量"的项目（官方管线、ComfyUI-Manager）都**不靠实时搜网**，而是用「已知 URL / 注册表」。唯一做实时搜网的是 ModelFinder，但它用浏览器自动化，**重且脆**——正是我们要规避的形态。

---

## 2. 国内镜像与独立模型站点（优先）

| 站点 | 形态 | 用法 / URL 规律 | 适合场景 |
|------|------|----------------|---------|
| **hf-mirror.com** | HF 反向代理（社区维护，2024 起稳定） | 设 `HF_ENDPOINT=https://hf-mirror.com`；URL 直接替换域名：`hf-mirror.com/{org}/{repo}/resolve/{branch}/{path}` | **首选**。ComfyUI 官方模型在 HF 的 `Comfy-Org/*` org 下 → 可直接镜像构造 URL，**无需搜索** |
| **ModelScope 魔塔社区** (modelscope.cn) | 阿里 **CN 原生 CDN**，比 hf-mirror 更稳；覆盖**官方/研究/模型族**极好（SDXL/SD3.5/Flux/LTX/VAE/CLIP），但**不镜像全部 HF 长尾**、且缺 Civitai 社区 LoRA 生态 | `modelscope` SDK（`snapshot_download`/`model_file_download`，续传/哈希校验，轻量）；`HubApi().search_model()` **搜索 API**；OpenAPI `/openapi/v1` 可纯 HTTP 调用；双站 cn/ai | **国内首选镜像（L2，与 hf-mirror 并列）** |
| **TUNA** (mirrors.tuna.tsinghua.edu.cn/huggingface) | 老牌镜像，偶有同步延迟 | 备选 | 兜底备选 |
| **Liblib** (liblib.ai) | 国内独立模型站，中文模型全 | 需其 API/页面；ModelFinder 中文名优先源 | 中文名模型回退源 |
| **Civitai** | 主流 SD/社区模型社区（LoRA/checkpoint/embedding 主力源），**无官方国内镜像**；但有**完备 REST API v1**（API+token 被官方许可，HTML 爬取反而是 ToS 违规） | `/api/v1/models?query=`（注：REST query 搜索 2025-05 起失效，需 Meilisearch）、`/model-versions/by-hash/{SHA256}`（**按哈希精确解析**，命中确切版本+下载 URL）、`/models/{id}` 取 files/downloadUrl/baseModel；需 `Authorization: Bearer` token，下载 URL 无镜像 | **社区/非官方模型的一线路径**（非兜底）；by-hash 精度最高 |

**核心洞察**：① **官方模型**（`Comfy-Org/*` 等）路径确定 → hf-mirror 确定性直链，不必搜索；② **社区/非官方模型**（Civitai 独占、用户自主发布的 HF 模型等）才是真实缺失模型的大头，无确定路径，必须靠 **Civitai API（by-hash 精确 / by-name 搜索）+ HF API** 解析；③ 许多社区模型也被作者同步到 HF → 若能解析出 HF repo，同样走 hf-mirror 提速。

---

### 2.1 ModelScope 重要等级评估（提级决策）

**结论：建议从 L4（长尾补充）提级到 L2（与 hf-mirror 并列的国内首选镜像）。**

- **覆盖度**：① 官方/研究/模型族模型（SDXL、SD3.5、Flux、LTX-2.3 视频、Qwen-Image、VAE/CLIP/text_encoders）覆盖极好，且 CN 原生——多个国内部署教程明确将其列为"国内首选下载源，无需翻墙、速度快、模型全覆盖"，对 CN 用户可靠性**高于** hf-mirror；② Civitai 社区 LoRA / 用户上传 checkpoint 生态弱（缺海量用户创作生态），这一块仍由 Civitai(L3) 覆盖。
- **程序化接入（成本低）**：SDK `pip install modelscope` → `snapshot_download`/`model_file_download`（续传/并发/重试/哈希，下载函数本身不依赖 torch）；`HubApi().search_model('query')` **搜索 API** 可兼作发现源；OpenAPI `/openapi/v1` 可纯 HTTP 调用免装 SDK；双站 `modelscope.cn`(国内默认)/`modelscope.ai`(国际)，catalog 与 token 站点隔离。
- **提级方案**：L2 镜像层 ModelScope 与 hf-mirror 并列，作为官方/研究模型**国内首选**（优先 ModelScope，hf-mirror 互备）；其 `search_model` 在 Civitai(L3) 失败时作长尾发现兜底；**不提级到 L3 社区主路径**（社区生态仍在 Civitai）。
- **配置**：`MODELSCOPE_ENDPOINT`(默认国内)、`MODELSCOPE_API_KEY`(公开读可不配，私有/限流时配)。

---

## 3. 精准匹配技术（轻 vs 重）

| 技术 | 成本 | 精度 | 结论 |
|------|------|------|------|
| **文件名归一化 + 别名表**（ModelFinder "不规则名称映射"：`SDXL_v1.0`→`sd_xl_base_1.0.safetensors`） | 极低（本地查表） | 高（已知模型） | **采用**，做 `name_aliases.json` |
| **已知注册表 / URL 构造**（filename → HF repo+path → 镜像 URL） | 极低（本地 JSON） | 高（官方/主流） | **采用**，核心层 |
| **元数据过滤**（node-type → category 路由到正确 `models/` 子目录） | 低 | 中高 | **采用**，复用官方 `getCategoryForNodeType` 思路 |
| **哈希精确解析**（SHA256 → Civitai `/model-versions/by-hash/{hash}` → 确切版本 + 下载 URL） | 低（一次 HTTP） | **极高**（文件级精确） | **采用，社区模型首选匹配**，比按名搜准得多 |
| **结构化 API 搜索**（Civitai Meilisearch / HF API / ModelScope API，by-name + baseModel 过滤） | 低（HTTP，非浏览器） | 中 | **采用，社区模型按名兜底**，替换 Google/DuckDuckGo 泛搜 |
| **哈希校验** | 低 | — | 仅用于下载完整性校验，非匹配 |
| **语义/向量相似度（embedding）** | **重（需模型/向量库）** | 高但过度 | **不采用**，违背轻量目标 |

**判定**：放弃泛网页搜索（Google/DuckDuckGo）与浏览器自动化（DrissionPage）；以「注册表 + 归一化 + 确定性镜像 URL（官方/社区-HF）」为主，社区/非官方模型走「**哈希精确解析 → 按名 API 搜索**」一线路径，而非兜底。

---

## 4. 轻量化方案架构（增量改造现有插件）

现有插件已具备：`core/searcher.py`（ModelSearcher + config）、`core/scanner.py`、`data/samples/`（kijai_all_models.txt、comfy_gguf_models.json，由 `build_models_db.py` 构建 SQLite）。**注册表种子已存在**，改造是"接管线"而非"从零建"。

### 4.1 分层解析（默认不搜网）
```
L0 本地匹配（现有）              → 扫 models/，文件名/变体/模糊相似度
L1 已知注册表（本地 JSON）        → filename → HF repo + path + category（种子：data/samples/ + 热门 Civitai + 官方）
L2 确定性镜像 URL（国内首选）     → 已知 repo 时：ModelScope（CN 原生，优先）或 hf-mirror.com/{repo}/resolve/main/{path}（覆盖官方 Comfy-Org 与社区-HF 模型）；二者互为兜底
L3 Civitai API（社区/非官方主力） → L3a by-hash：计算/已知 SHA256 → /model-versions/by-hash → 精确版本+URL；
                                     L3b by-name：Meilisearch + baseModel 过滤 → 候选排序；
                                     优先探测是否同步到 HF，是则回退 L2 提速；CivArchive 作删除模型镜像兜底
L4 其他发现 API（HF API / ModelScope search_model） → 长尾补充 / Civitai 失败兜底
```
- L0–L2 默认跑；**L3 对社区/非官方模型是默认开启的一线路径**（非 opt-in 兜底），仅 L4 按需。
- 移除 Google / DuckDuckGo 泛网页搜索分支。

### 4.2 镜像优先下载
- 读取 `HF_ENDPOINT`（CN 用户默认 `https://hf-mirror.com`）、`MODELSCOPE_ENDPOINT`。
- 所有 HF 派生 URL 经镜像域名重写；下载引擎支持 aria2 / 续传（参考 `manager_downloader.py`）。

### 4.3 智能落盘路由
- node-type → category（复用官方 `getCategoryForNodeType` 逻辑）→ 落到正确 `models/` 子目录（checkpoints/loras/vae/...）。复用现有 `model_mover` 归类能力。

### 4.4 别名/归一化表
- 新增 `core/data/name_aliases.json`（不规则名称映射），提升已知模型命中率，零网络。

### 4.5 形态与依赖
- 保持 ComfyUI custom_nodes 形态；**不引入 Chrome / DrissionPage**。
- 依赖收敛为 `requests`/`aiohttp`（HTTP）+ 可选 `aria2`；不引入 ML/向量库。

---

## 5. 实施路线图（增量，复用现有代码）

| 阶段 | 任务 | 复用/产出 |
|------|------|----------|
| P1 | 规整注册表 `core/data/model_registry.json`（官方 Comfy-Org + 热门 Civitai + data/samples/ 种子） | 复用 `build_models_db.py` |
| P2 | 实现 L1/L2 解析：注册表查表 + hf-mirror URL 构造 | 改 `core/searcher.py` |
| P3 | 镜像端点接入（`HF_ENDPOINT`/`MODELSCOPE_ENDPOINT`）+ aria2 续传下载 | 改下载器 |
| P4 | node-type→category 智能落盘路由 | 复用现有归类 |
| P5 | 别名归一化表 `name_aliases.json` | 新增 |
| P6 ✅ | Civitai API 接入：by-hash 精确解析 + by-name(Meilisearch) 搜索 + CivArchive 兜底；移除 Google/DuckDuckGo 泛搜 | 改 `core/searcher.py`（Civitai by-hash/by-name 此前已实现；本 PR 移除 `GoogleOmniProvider` / `DuckDuckGoProvider` 泛搜分支） |
| P7 ✅ | 文档：更新 `docs/`（架构/用法），PR 合入 | 走 Push Gate（本 PR 执行，AGENTS/README/ARCHITECTURE/PROJECT_BRIEF 同步去 Google/DuckDuckGo） |

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 长尾模型不在注册表 → L1/L2 命中失败 | L3 Civitai API（by-hash/by-name）+ L4 HF/ModelScope API 兜底（仍轻于浏览器/泛搜） |
| ModelScope 不镜像全部 HF 模型（尤其缺 Civitai 社区 LoRA 生态） | 已提级 L2 国内首选镜像（官方/研究模型）；社区模型仍由 Civitai(L3) 覆盖；长尾用其 search_model 兜底 |
| Civitai 无国内镜像，下载速度受 CN 网络制约（**搜索/解析不受影响**） | 解析照常；下载优先探测 HF 镜像源，否则提示代理/手动；不阻塞主流程 |
| Civitai REST `query=` 搜索 2025-05 失效 | 改用 Meilisearch 搜索端点；by-hash 不依赖搜索，优先用 |
| Civitai 限流（429）/ 需 token 取下载 URL | 指数退避 + 可选 token 配置；未配 token 时仅能解析、下载提示手动 |
| 社区模型 license 各异（含非商用限制） | 解析结果标注 license，下载/商用前提示用户 |
| 注册表维护成本 | 初始种子来自 `data/samples/` + `Comfy-Org/*` 官方 + 热门 Civitai（路径确定、更新少）；社区可补充 |

---

## 7. 结论

**方案可行且轻量**：以「已知注册表 + 确定性镜像 URL（官方/社区-HF）+ Civitai API 解析（by-hash 精确 → by-name 搜索）」为主路径，彻底替代泛网页搜索与浏览器自动化。官方模型只是一块（确定性直链），社区/非官方模型（Civitai 等）才是多数，由 API 按哈希精确解析覆盖。本项目已有 `data/samples/` 注册表种子与 `core/searcher.py` 框架，改造为增量接线，无需引入重依赖。优先级：P1→P2→P3（注册表+镜像+落盘）即可交付核心；**P6（Civitai by-hash）是"精准匹配"的关键增量**。

---
*调研来源：Exa（comfyui-modelsearchandload / ComfyUI-ModelFinder / Comfy-Org missingModelPipeline 等）、GitHub、hf-mirror.com 实战手册、ModelScope 文档、ComfyUI-Manager 机制文档、ComfyUI-Lora-Manager(DepthWiki civitai 集成)、Civitai REST API v1 文档 / civitai-mcp、CSDN/头条国内镜像教程。*

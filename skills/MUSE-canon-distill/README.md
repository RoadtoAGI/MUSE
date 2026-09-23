# MUSE-canon-distill

**MUSE 姊妹扩展包：从经典文学作品反向蒸馏 AI 写作可用素材**。

`MUSE-writing` 负责"从 0 写原创故事"；本包负责"从已有名著拆出素材，喂给写作流程做参考"。两个 plugin 独立加载，组合后形成"参考名著 → 写自己的故事"完整能力。

## 能力

| Skill | 做什么 |
|---|---|
| [`scene-reference`](skills/scene-reference/) | 按当前创作问题检索名著场景，供正文写作或独立场景取材；主控按实际需要调用 |
| [`design-doc-reference`](skills/design-doc-reference/) | 在 Phase 0–5 按当前设计问题读取已有逆向分析与灵感卡，保留来源条件和采用范围 |
| [`dialogue-reference`](skills/dialogue-reference/) | Phase 6 按场景关系、压力和言语行动检索连续对白回合，给每个角色生成独立的行为型 few-shot |
| [`dialogue-kb-distill`](skills/dialogue-kb-distill/) | 从一部已入库作品提取可核验的对白事件，更新场景覆盖与检索索引 |
| [`character-kb-distill`](skills/character-kb-distill/) | 从名著语料蒸馏角色知识参考包，保留来源、关系与行为依据，供写作侧角色构建使用 |
| [`novel-analysis`](skills/novel-analysis/) | 名著结构分析——产出场景切片、节拍标注、人物档案等 KB 资产，喂给上面两个 skill |
| [`drama-analysis`](skills/drama-analysis/) | 戏剧、戏曲与剧本的 medium-aware 分析，产出场景、人物与对白资产 |

## 资源

- [`knowledge-base/novels/`](knowledge-base/novels/) — **小说语料库**；实际作品与处理状态以 `knowledge-base/dialogue/corpus_registry.yaml` 为准
- [`knowledge-base/dramas/`](knowledge-base/dramas/) — 戏剧与剧本语料
- [`knowledge-base/dialogue/`](knowledge-base/dialogue/) — 对白经典书目骨架、语料登记表、事件索引、人物原型索引与覆盖报告
- [`knowledge-base/embeddings/`](knowledge-base/embeddings/) — 基于语料生成的 scene embeddings（`scene_index.json` + `scene_embeddings.npy`）
- [`knowledge-base/scripts/`](knowledge-base/scripts/) — KB 操作工具；对白链使用 `dialogue_kb.py` 建库和核验，使用 `dialogue_query.py` 做无 API 的结构化检索

## 语料来源与删除请求

本仓库内已含预蒸馏作品；数量、媒介与覆盖状态以 registry 和 coverage report 为准。小说与戏剧文本来自公开网络资源，相关权利仍归原作者及出版方所有。

权利人如认为某项内容不应继续保留，可通过仓库 Issue 联系维护者并说明作品与版本信息。核实后将删除对应原文以及由该作品生成的场景、索引和向量资产。

## Python 依赖

```
pyyaml>=6.0
numpy>=1.24
openai>=1.0          # kb_query.py 生成 query embedding
python-dotenv>=1.0   # 加载 OpenAI API key
```

## API 配置

### 可选 JEV 检索增强

2026-09-23 发布：技能包 **v0.9.0**，配套 **muse-runtime v0.1.0**。运行包可从 [GitHub Release](https://github.com/RoadtoAGI/MUSE/releases/tag/muse-runtime-v0.1.0) 下载，也可在选定的 Python 环境安装：

```bash
python3 -m pip install "git+https://github.com/RoadtoAGI/MUSE.git@muse-runtime-v0.1.0"
```

默认使用 `standard`。在执行查询的同一 Python 环境安装 `muse-runtime`；开发环境可执行 `python3 -m pip install /path/to/MUSE`，K 独立安装使用该项目构建的 `muse_runtime-0.1.0-py3-none-any.whl`。运行包只依赖 PyYAML，不依赖仓库相邻目录；标准查询无需安装它。

执行环境通过 `MUSE_JEV_API_KEY` 提供 JEV key，再按作品设置：

```bash
muse mode set jev --work-dir /absolute/path/to/work
muse mode status --work-dir /absolute/path/to/work
muse mode set standard --work-dir /absolute/path/to/work
```

官方优先使用 `MUSE_JEV_API_KEY`；额度不足或限流时自动改用 `MUSE_JEV_TUZI_API_KEY` 指定的 Tuzi 备用通道。每通道至多尝试一次，同一批次切换后续用备用，新批次恢复官方优先；状态与日志保留实际通道、模型和失败原因。完整切换规则见 `python3 -m muse_runtime brainstorm guide` 中的“官方优先与备用通道”。

模式保存在该作品的 `.muse/runtime.yaml`。查询显式传 `--work-dir`，或由既有 `<work>/pipeline/...` 输出位置绑定；无绑定沿标准模式。不按 cwd 或系列目录继承。`set/status` 不验证 key，也不发请求；status 的 mode 表示配置，recent 显示实际评价和交付状态。

需要工作台的新作品默认值时，可由启动环境提供 `MUSE_NEW_WORK_TEMPLATE=/absolute/path/to/workbench/.muse/runtime.yaml`。MUSE 的长短篇、系列和章初始化脚本仅在创建新目录时复制 mode；已有作品不覆盖，查询期仍只读自己的 mode 文件。模板只含 mode，密钥继续由执行环境提供。

JEV 在 `kb_query.py`、`inspiration_query.py` 内部评价候选，选中的原文与卡片照常落盘，评分只写 `.muse/jev-events.jsonl`。场景默认按适配 Score 排序；显式 MMR、带 `--preferred-work` 的灵感查询只评价并保留原顺序。手选 `--select`、`--read-card` 和无 signals 的阶段浏览沿原路径。两个查询器均接受可重复的 `--must`，每个条件独立评价；首批排序使用 Score，条件概率留作诊断，尚未启用加权组合。

开启后，查询、风格/功能提示、必要条件及允许使用的候选原文或卡片会发送到 **TypeSafe**，可能包含查询中的未发表内容和私有语料。首批不装载角色视图。来源与用途限制在发送前执行；参考文件保持原格式，不增加 writer 的评分上下文。standard 不发 JEV 请求。切回 standard 影响后续查询，已选参考按既有生命周期继续使用。

缺运行包或 key 会给出配置错误；网络、限流、超时或无效响应触发整批原顺序回退。最多 3 并发，单请求 socket timeout 上限 8 秒，批次最多等待 15 秒后取消未开始项；已在执行的 HTTP 线程可能延后结束，进程退出会等待这些线程。日志写失败不阻断参考交付。CLI 配置、运行记录与写作材料互相独立，记录 delivered 仅表示已交付，不表示 writer 已读取。

### 场景 embedding

`kb_query.py --query` 调远程 embedding API 计算 query 向量，使用前需配置 API key。`--select` 物化已知作品与场景，以及对白结构检索可在本地完成。

**一键诊断**：

```bash
python3 knowledge-base/scripts/kb_setup_check.py
```

四步检查（依赖 / KB 资产 / API 配置 / 真实连通性）+ 明确 → 修复指引。

**配置三种方式**：

```bash
# 方式 A：shell 临时 export（单次会话）
export MUSE_KB_API_KEY='sk-...'

# 方式 B：持久化（推荐写进 ~/.bashrc 或 ~/.zshrc）
echo "export MUSE_KB_API_KEY='sk-...'" >> ~/.bashrc

# 方式 C：.env 文件（项目隔离）
cp .env.example .env
# 编辑 .env 填入真实 key（.env 已加入 .gitignore，不会被 commit）
```

环境变量名（按优先级）：
- `MUSE_KB_API_KEY`
- `MUSE_KB_BASE_URL`（可选，默认通用占位地址）→ 兼容旧名 `API_BASE_URL`

**安全提醒**：`.env` 已加入 `.gitignore`；不要把 API key 写进 commit / 公开 issue / 截图 / `.env.example` 模板。

## 复现时重建 embeddings

复现者使用现有处理后知识时，应在目标环境中重新合并场景索引并重建 content/style 两个 embedding 通道。索引构建与查询必须使用同一个 embedding 模型。

```bash
export MUSE_KB_API_KEY='...'
export MUSE_KB_BASE_URL='https://your-compatible-endpoint.example/v1'
export MUSE_KB_EMBEDDING_MODEL='your-embedding-model'
python3 knowledge-base/scripts/merge_scene_index.py
python3 knowledge-base/scripts/build_embeddings.py --channel all
python3 knowledge-base/scripts/kb_setup_check.py
```

增删作品、修改单作品 `scene_index`、场景文本、style annotation 或 embedding 模型后均须重建。该步骤会调用所配置的 embedding 服务，并可能产生 API 费用。

## 与 MUSE-writing 的衔接

主干 `MUSE-writing` 的 `phase6-scene-development` 按当前设计决定参考需要，dispatch 将本次有效参考路径传给 writer：

- `scene-reference` 产出 `pipeline/references/{sid}_ref.md`；已取得且仍适用的材料可继续使用，由主控传递实际路径
- Phase 6 在每个角色排练前调用 `dialogue-reference`，产出 `pipeline/references/{sid}_{role_slug}_dialogue_ref.md`；角色 agent 只迁移互动机制
- phase6 [execution-protocol §3.5](../MUSE-writing/skills/phase6-scene-development/references/execution-protocol.md) 描述参考采用与用途契约
- 主干 plugin 单独运行时这些扩展点静默跳过，不影响主线

存在 Phase 0 时，`kb_query.py --canon-reference-profile <当前 YAML 绝对路径>` 按 `user_reference_materials[].work` 精确绑定各作品用途。`--reuse-mode` 与 `--intended-domains` 表示本次共同限制；每条 `reference_scope` 保留实际用途与最终档位，总头仅汇总。`style_only` 限于表达，明确强复用继续使用贴切素材；分数与手选均不能扩大作者指定范围。复合题材写入 `--query`，`--genre` 留给作者明确的硬限制。

## 知识库维护

手艺标注以作品权威索引的 `craft_notes_file` 为优先来源，未声明时兼容 `craft_notes/scene_*_beats.md`；提取脚本在该 Markdown 旁写 YAML，查询优先读取结构化标注、缺失时读取原标注。

逐作品提名维护来源解释与原文窗口；灵感卡维护跨作品机制、身份与适用条件。`build_inspiration_cards.py --stage cluster --prepare` 同时装配这两层，成卡来源由提名汇入。修订单作品解释时先同步该作品提名，跨作品关系修订保留在卡中。`--replace` 整批校验通过后才替换卡与重建派生索引，含拒收条目时原库保持原样。

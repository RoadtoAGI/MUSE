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

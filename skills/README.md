# MUSE Skills Collection

This directory contains the skill packages that make up MUSE, an AI-assisted creative-writing system grounded in narrative theory, literary analysis, and reproducible writing workflows. The collection covers original fiction, derivative writing, long-form serial writing, and the distillation of literary works into reusable scene, character, style, and structural references.

## Package Overview

| Package | Purpose |
|---|---|
| [`MUSE-writing/`](MUSE-writing/) | The creative-writing package for complete original short and medium-length fiction and screenplay writing. Its full workflow progresses from conception through world, character, spine, structure, scene planning, drafting, and integration. |
| [`MUSE-canon-distill/`](MUSE-canon-distill/) | The literary knowledge-base package. It analyzes novels and plays, retrieves scenes as writing references, distills character material, and produces structured design assets from source texts. |
| [`MUSE-serial-writing/`](MUSE-serial-writing/) | A system for serial and derivative fiction, including fan fiction, sequels, spin-offs, and stylistic adaptation, with volume and chapter planning, continuity checks, persistent story state, and incremental publication. |
| [`MUSE-serial-distill/`](MUSE-serial-distill/) | A forward-looking analysis package for long and ongoing serial fiction. It produces serial-writing reference patterns or a structured handover package for continuing an existing series. |

`MUSE-canon-distill` supplies literary references to `MUSE-writing` and `MUSE-serial-writing`. `MUSE-serial-distill` supplies reference and takeover assets to `MUSE-serial-writing`.

## Knowledge Base

The knowledge base is primarily in Chinese. Most source texts, annotations, skill instructions, and generated analysis artifacts use Chinese. English titles may therefore lead to Chinese translations or Chinese-language annotations unless an entry is explicitly marked as English below.

### English Reviewers: Direct Corpus Access

The following entries contain English source text and are convenient starting points for English-speaking reviewers:

| Work | Direct English Text | Corpus Entry |
|---|---|---|
| Richard Matheson, *I Am Legend* | [`full_text.md`](MUSE-canon-distill/knowledge-base/novels/I%20Am%20Legend/full_text.md) | [`novels/I Am Legend/`](MUSE-canon-distill/knowledge-base/novels/I%20Am%20Legend/) |
| William Shakespeare, *Macbeth* | [`full_text.md`](MUSE-canon-distill/knowledge-base/dramas/Macbeth/full_text.md) | [`dramas/Macbeth/`](MUSE-canon-distill/knowledge-base/dramas/Macbeth/) |

These corpus entries also contain scene divisions and structured analysis assets. Some generated annotations remain in Chinese.

### Literary Collection Highlights

The corpus brings together works with distinct narrative traditions and craft value:

| Area | Representative Works | Brief Introduction |
|---|---|---|
| Chinese modern literature | *The True Story of Ah Q*, *White Deer Plain*, *A Kind of Reality*, and *Thunderstorm* | Satire, family and social history, psychological violence, and modern Chinese tragedy. |
| Chinese science fiction | The *Remembrance of Earth's Past* trilogy and *The Wandering Earth* | Large-scale worldbuilding, civilization-level conflict, technological imagination, and moral choice under extreme pressure. |
| Wuxia and historical fiction | *The Legend of the Condor Heroes*, *The Return of the Condor Heroes*, and *Great Tang: Li Bai* | Martial ethics, heroic development, romance, and the interaction between individual lives and historical change. |
| World literature | *Jane Eyre*, *The Red and the Black*, *Norwegian Wood*, *Stoner*, *The Moon and Sixpence*, *2666*, and *The Road* | Interior life, class ambition, alienation, artistic obsession, fragmented narrative, and survival. Most entries in this group are Chinese translations. |
| Epic fantasy and multi-thread narrative | *The Lord of the Rings* and the first five volumes of *A Song of Ice and Fire* | Secondary-world construction, mythic structure, political conflict, ensemble casts, and multi-POV plotting. |
| Drama and dark speculative fiction | *Hamlet*, *Macbeth*, and *I Am Legend* | Tragic causality, ambition, isolation, dramatic escalation, and the redefinition of the human or monstrous. |

The knowledge base also includes contemporary and serial-fiction samples used to study genre conventions, chapter rhythm, hooks, continuity, and long-form narrative development.

### Resource Provenance

The source-text resources bundled in the knowledge base were collected from publicly accessible online sources, including **eLibrary**. MUSE-generated assets—including scene slices, indices, YAML analyses, character files, and craft notes—were derived from those source texts by the included skills and scripts.

The underlying rights remain with the respective authors and publishers. Rights holders who believe that a bundled work should be removed may contact the maintainers through a repository issue; the corresponding source text and derived index assets will be removed after verification.

### Rebuild Retrieval Embeddings

When reusing the processed knowledge assets, rebuild the aggregate scene index and embeddings in the target environment. Embeddings are derived snapshots tied to the selected knowledge files, embedding provider, and model; keep the same embedding model for index construction and query-time retrieval.

```bash
cd MUSE-canon-distill
export MUSE_KB_API_KEY='...'
export MUSE_KB_BASE_URL='https://your-compatible-endpoint.example/v1'
export MUSE_KB_EMBEDDING_MODEL='your-embedding-model'
python3 knowledge-base/scripts/merge_scene_index.py
python3 knowledge-base/scripts/build_embeddings.py --channel all
python3 knowledge-base/scripts/kb_setup_check.py
```

The build command calls the configured embedding service and may incur provider charges. Rebuild whenever the included works, per-work scene indices, scene text, style annotations, or embedding model change.

## Directory Structure

```text
skills/
├── README.md
├── MUSE-writing/
│   ├── skills/                 # Original-writing entry points, phases, and craft/review skills
│   ├── agents/                 # Subagent role definitions
│   ├── scripts/                # Workflow, validation, and assembly utilities
│   └── hooks/                  # Runtime checks and workflow automation
├── MUSE-canon-distill/
│   ├── skills/                 # Novel/drama analysis, retrieval, and distillation skills
│   ├── agents/                 # Knowledge-base annotation roles
│   └── knowledge-base/
│       ├── novels/             # Novel source texts and structured assets
│       ├── dramas/             # Drama source texts and structured assets
│       ├── embeddings/         # Retrieval indices and vector data
│       ├── inspiration/        # Reusable inspiration cards and backlinks
│       └── scripts/            # Extraction, annotation, retrieval, and verification tools
├── MUSE-serial-writing/
│   ├── skills/                 # Serial outline, chapter writing, review, and continuity skills
│   ├── agents/                 # Serial-writing subagent roles
│   ├── scripts/                # Series-state and chapter-lifecycle utilities
│   └── hooks/                  # Workspace validation and published-content protection
└── MUSE-serial-distill/
    ├── skills/                 # Serial analysis, reference, and takeover skills
    ├── agents/                 # Knowledge-base annotation roles
    ├── scripts/                # Chapter splitting and export validation
    └── knowledge-base/         # Generated serial-fiction corpus assets
```

Each package has its own README and plugin metadata. Individual skill behavior is defined in `skills/<skill-name>/SKILL.md`, while `references/` directories hold schemas, templates, theory excerpts, examples, and detailed execution protocols. A package may also include `.claude-plugin/` and `.codex-plugin/` metadata for its supported runtime environments.

## Suggested Review Path

1. Read the package-level README for scope and intended use.
2. Open the relevant `skills/<skill-name>/SKILL.md` to inspect inputs, workflow, outputs, and acceptance criteria.
3. Review `scripts/` and `hooks/` for mechanical validation and runtime enforcement.
4. Use the English corpus links above for a source-text-level review without first navigating the primarily Chinese knowledge base.

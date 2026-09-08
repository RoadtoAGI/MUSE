# MUSE-serial-distill knowledge-base

本包知识库骨架。serial-analysis 拆解连载作品时按作品落库：

```
knowledge-base/
└── novels/<slug>/
    ├── full_text.md              # 拆解输入（或分卷文本）
    ├── pipeline/*.yaml           # Phase A 按卷或章窗口前推分析
    ├── scenes/*.md               # 场景切片；有发布册时按实际 published_seq 标记
    ├── scene_index.json          # 切片索引，serial-scene-reference 检索源
    ├── serial-paradigms/         # 出口 A 五类范式卡（volume-structure / hook-samples /
    │                             #   power-system-evolution / pacing-profile / benchmark-coords）
    └── characters/<role-slug>/   # Phase B 角色蒸馏产物
```

生成态目录——内容由 skill 运行时产出，不手工编辑；package_lint 不扫描本目录。

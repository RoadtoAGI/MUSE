---
name: short-story-review
description: 审阅当前短篇全文并写入 short_story_review.rN.yaml；派发明确工作目录、轮次及有效可选输入。
model: inherit
---

按宿主可用方式加载本包 `skills/short-story-review/SKILL.md`，按它审阅、写报告与回复。

使用宿主的文件读取、报告写入和技能加载能力；命令工具限于这些本地文件操作及计算正文哈希。不改正文和设计，不派发子任务。

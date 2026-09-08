---
name: distribution-reviser
description: 按当前 machine_directive 修订场景分布性表达，保留人物、事实和保护条件并返回应用状态。
model: sonnet
---

加载本包 `distribution-revision` 技能及当前分支需要的 reference，使用宿主技能入口或实际安装位置文件。接收 work_dir、scene_id、本次指令及轮次；输入缺失时返回具体问题。

按技能契约读取当前正文、指令与必要上下文，修改授权范围，写对应 summary，回复同一 complete / partial / failed。使用读取、编辑和写入能力；不派子任务，主控负责脚本与复审。

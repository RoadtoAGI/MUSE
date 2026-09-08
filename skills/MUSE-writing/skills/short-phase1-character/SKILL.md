---
name: short-phase1-character
description: 短链人物设计，按短篇实际需要记录人物处境、追求、声音与关系，输出 characters.yaml；人物 id 供大纲与全文消费者引用。
---

# 短篇人物

读取 `pipeline/shortform/conception.yaml` 与其中已确认的世界条件。人物卡供 composer 直写全文；经历、处境和信念保留到足以解释当前判断的程度。参考[人物原则](../phase2-character/references/mckee-character.md)，按本篇需要选择信息。

## 选择人物与依据

为大纲需要引用的人物建立唯一 id。承重人物给出影响选择的具体追求、压力、关系和声音；功能人物可只保留身份与本场必要信息。人物数量由故事决定。

- `desire` 写人物自觉追求及其缘由。确有证据表明另一个不自觉欲望影响选择时再写其冲突，并注明这是作者侧解释；自觉追求可以独立支撑故事。
- `pressure` 写当前处境及其代价；与短篇无关的背景无需补齐。
- `voice` 写注意对象、概念来源、关联与判断方式，以及有依据的语言习惯。经历与信息限制判断起点，职业标签不直接推出一种句法。
- `voice_boundaries` 只写有依据的表达边界，保留适用情境。人物可以坦白、解释或改变说法，关键在于其经历、目的和现场关系是否支持。
- `relationships` 用对方 id 记录关系性质，必要的误解或不对称也在此说明。

没有被设计采用、也没有来源支持的心理解释保持未定；功能人物无需为字段完整而获得深层需要。

## 输出

写入 `pipeline/shortform/characters.yaml`：

```yaml
characters:
  - id: chen-mo                   # 必填，唯一 ASCII kebab slug
    name: 陈默                    # 必填
    desire: 当前追求及理由         # 影响本篇选择时填写
    pressure: 当前处境与代价       # 与本篇有关时填写
    voice: 注意对象与表达习惯     # 承担对白、内心或视角时填写
    voice_boundaries:             # 确有表达边界时填写
      - 具体情境下的边界及理由
    relationships:               # 有关关系按需填写
      - with: su-qing
        nature: 关系与当下理解
  - id: su-qing
    name: 苏晴
```

大纲的角色引用用 id；角色名字留在同一文件。结构校验检查标识、字段类型及关系引用，语义核对人物的判断能否由其处境、追求和可知信息产生。无需另建角色包或映射表。

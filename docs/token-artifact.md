# Moss Token Artifact — AI Efficiency Format v1

**版本**: alpha(t)1  
**状态**: 技术规范  

---

## 概述

Token Artifact 是 Trust Artifact 的对偶技术。Trust Artifact 回答"这个代码能信吗"，Token Artifact 回答"AI 能一眼看懂这个文件吗"。

通过结构化骨架，Token Artifact 将 Moss 文件的完整语义压缩到 10-30 tokens。

## 命令

```
moss token <file>              别名: moss token-artifact
moss token --level <level>     输出粒度
moss token-diff <a> <b>        两个版本的差异
```

## 三级粒度

### brief (~10-15 tokens)

```json
{
  "ta": "ta.v1",
  "v": "alpha(t)1",
  "f": "order",
  "h": "dad1930f601b",
  "c": {"e": 1, "t": 2, "l": 2},
  "r": [{"n": "canShip", "io": "Order→Bool"}],
  "t": true
}
```

用途：AI 批量扫描目录时读取。只提供"有没有 effect？多少个 type？几个规则？信任状态"。

### normal (~20-30 tokens)

```json
{
  "ta": "ta.v1",
  "v": "alpha(t)1",
  "f": "order.moss",
  "h": "dad1930f601b44ec",
  "c": {"e": 1, "t": 2, "l": 2},
  "r": [{"n": "canShip", "in": {...}, "o": "true", "at": "order.moss:10"}],
  "g": true,
  "s": true,
  "t": true
}
```

用途：AI 需要理解文件功能时读取。包含规则签名、输入/输出、位置。

### full (~50 tokens)

```json
{
  "v": "alpha(t)1",
  "t": true,
  "h": "dad1930f601b44ec",
  "c": {"e": 1, "t": 2, "c": 2},
  "tr": 1,
  "g": true,
  "sh": true
}
```

用途：AI 在不需要完整 Trust Artifact 时使用。`--summary` 格式的别名。

## token-diff

```
moss token-diff file_a.moss file_b.moss
```

输出两个版本的差异字段：

```json
{
  "files": ["a.moss", "b.moss"],
  "changed": ["hash", "golden"],
  "details": {
    "golden": {"from": true, "to": false}
  }
}
```

## 字段说明

| 字段 | 简写 | brief | normal | full | 说明 |
|------|------|-------|--------|------|------|
| `ta` | ta | ✓ | ✓ | — | 格式标记 `ta.v1` |
| `v` | v | ✓ | ✓ | ✓ | Moss 版本 |
| `f` | f | ✓ | ✓ | — | 文件名 |
| `h` | h | ✓(12) | ✓(16) | ✓(16) | SHA-256 前 N 字符 |
| `c.e` | c.e | ✓ | ✓ | ✓ | effect 数量 |
| `c.t` | c.t | ✓ | ✓ | ✓ | type 数量 |
| `c.l` | c.l | ✓ | ✓ | — | callable 数量 |
| `c.c` | c.c | — | — | ✓ | callable 数量 |
| `r` | r | ✓(简化) | ✓(完整) | — | 规则列表 |
| `r[].n` | n | ✓ | ✓ | — | 规则名 |
| `r[].io` | io | ✓ | — | — | 输入→输出简写 |
| `r[].in` | in | — | ✓ | — | 规则参数 |
| `r[].o` | o | — | ✓ | — | 规则结果 |
| `r[].at` | at | — | ✓ | — | 源码位置 |
| `g` | g | — | ✓ | ✓ | golden gate |
| `s` | s | — | ✓ | — | selfhost gate |
| `sh` | sh | — | — | ✓ | selfhost gate |
| `tr` | tr | — | — | ✓ | trace 事件数 |
| `t` | t | ✓ | ✓ | ✓ | trust 总判定 |

## Token 节省估算

以 `order.moss` 为例：
- 源码：~200 tokens
- Token Artifact full：~50 tokens（75% 节省）
- Token Artifact normal：~25 tokens（87% 节省）
- Token Artifact brief：~12 tokens（94% 节省）

## 与 Trust Artifact 的关系

| | Trust Artifact | Token Artifact |
|---|---|---|
| 问题 | 可验证吗 | 能看懂吗 |
| 格式 | 完整 JSON (5 gate) | 结构骨架 |
| 命令 | `moss artifact` | `moss token` |
| 典型 tokens | 50-200 | 10-30 |
| 用途 | CI/审计/签名 | AI 扫描/理解/批量读取 |

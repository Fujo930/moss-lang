# Moss Trust Server — API Reference

**版本**: alpha(t)3  
**服务**: `moss serve (--host 127.0.0.1 --port 9876)`

---

## 端点

### POST /api/trust

完整信任验证。接收 Moss 源码，返回结构化信任报告。

**查询参数**: `?level=auto|brief|normal|full`

| level | 返回 | token |
|-------|------|-------|
| `auto` | trust=true → brief, trust=false → normal+fix_hints | ~15/40 |
| `brief` | 6 字段精简报告 | ~15 |
| `normal` | 信任状态 + fix_hints + 失败 gate | ~40 |
| `full` | 完整五 gate 报告 | ~200 |

**请求**:
```
POST /api/trust?level=auto
Content-Type: text/plain

rule double(x) = x * 2
```

**响应 (auto, trust=true)**:
```json
{"trust":true, "h":"dad1930f601b", "g":5, "c":{"e":1,"t":2,"l":2},
 "r":[{"n":"canShip","v":"true"}], "ms":53, "ta":"ta.v1"}
```

**响应 (auto, trust=false)**:
```json
{"trust":false, "g":2, "failed_gates":["check"], "check":false,
 "fix_hints":[{"line":1,"hint":"Add uses clause to function signature."}],
 "token":{"effects":1,"types":0,"callables":1}, "h":"b80792336156", "ms":42}
```

### POST /api/token

轻量结构提取。仅解析+检查，不编译、不执行 VM。

**查询参数**: `?level=brief|normal`

| level | token | 说明 |
|-------|-------|------|
| `brief` | ~10 | 极简结构骨架 |
| `normal` | ~20 | 规则标记 + fix_hints |

**性能**: ~3ms（比完整的 trust 快 25 倍）

### POST /api/trust-batch

批量信任验证。接收多文件 JSON，一次返回所有文件的状态。

**请求**:
```json
{
  "files": {
    "main.moss": "fn greet() { print(\"hello\") }",
    "lib.moss": "fn add(x, y) = x + y"
  }
}
```

**响应**:
```json
{
  "total": 2, "passed": 2, "failed": 0,
  "files": {
    "main.moss": {"trust":true, "g":4, "h":"b80792336156", "ms":42},
    "lib.moss": {"trust":true, "g":4, "h":"f9138a4b2e01", "ms":31}
  }
}
```

失败文件会附带 `failed_gates` 和 `fix_hints`。

### GET /api/health

```json
{"status":"ok", "moss":"alpha(t)3", "cached_entries":42,
 "server":"MossTrustServer/alpha(t)3"}
```

---

## AI agent 集成示例

```python
# AI 生成代码后自动验证
import requests, json

source = "fn update(o) uses Database { dbPut(o.id, o) }"
r = requests.post("http://localhost:9876/api/trust?level=auto", data=source)

if r.json()["trust"]:
    print("✓ code is trusted, gates:", r.json()["g"])
else:
    fails = r.json()["failed_gates"]
    hints = r.json()["fix_hints"]
    print(f"✗ {len(fails)} gate(s) failed: {fails}")
    for h in hints:
        print(f"  line {h['line']}: {h['hint']}")
```

---

## 与 moss CLI 的关系

| 功能 | CLI | API |
|------|-----|-----|
| Trust 验证 | `moss artifact` | `POST /api/trust` |
| Token 提取 | `moss token` | `POST /api/token` |
| Token diff | `moss token-diff` | — |
| Trust 签名 | `moss artifact-sign` | — |
| 批量验证 | — | `POST /api/trust-batch` |
| **Trust header** | `moss token --header` | — |
| **Decompile** | `moss decompile` | — |

CLI 和 API 各有所长：CLI 做离线操作（签名、diff、header、decompile），API 做在线验证（单文件/批量 trust、token 提取）。

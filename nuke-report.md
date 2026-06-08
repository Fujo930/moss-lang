# Moss 0.56.2 — 无差别饱和攻击报告

**攻击对象**: Moss `ds-Mosslang` v0.56.2  
**攻击方法**: 全向量无差别饱和攻击  
**攻击向量数**: 40  
**攻击日期**: 2025-07-16  

---

## 攻击面地图

```
┌─────────────────────────────────────────────────────────┐
│                    攻击向量分布                          │
├──────────────┬──────────┬──────────────────────────────┤
│  词法层 (4)   │ A2,A6,A23,A26 │ 零宽字符/长字符串/BOM/空字节   │
│  语法层 (7)   │ A4,A5,A7,A11,A16,A28,A30 │ 深度嵌套/注释注入/插值/密集语法 │
│  检查器 (6)   │ A1,A3,A12,A24,A27,A39 │ 类型/规则纯度/effect/递归类型 │
│  运行时 (6)   │ A8,A14,A15,A21,A31,A33 │ 精度/边界/null/update   │
│  自托管 (3)   │ A13,A28,A35 │ 箭头函数/全面语法/赋值箭头       │
│  Trust管线 (5)│ A9,A18,A22,A36,A37 │ trust-verify/金文件/捆绑包  │
│  项目系统 (3) │ A10,A19,A38 │ 导入循环/路径穿越               │
│  其他 (6)     │ A17,A20,A25,A29,A32,A34 │ 同形字/货币/lambda/换行  │
└──────────────┴──────────┴──────────────────────────────┘
```

---

## 🔴 致命发现

### F1: trust-verify 不重新执行 gates (Critical)

`moss trust-verify` **只检查哈希匹配，不重新执行信任门**。  

**PoC**:
```bash
# 1. 为干净文件生成 trust bundle
moss trust ../nuke_tests/A38_path_traversal.moss > clean.json
# 2. 篡改 bundle: 修改 file 指向恶意文件, 更新 source_sha256 为恶意文件的哈希
# 3. trust-verify 说 PASS — gates 从未在恶意文件上执行!
moss trust-verify tampered.json
# → PASS: bundle hash matches source
```

**根本原因**: `run_trust_verify()` (cli.py:748-803) 仅执行 `hashlib.sha256(source).hexdigest() == stored_hash`，不调用 `check_program() / compile_program() / VM / compare_selfhost_details()`。

**影响**: trust bundle 完全失去完整性保证。任何拥有 bundle 写入权限的攻击者都可以替换源代码并重新计算哈希，使 bundle 表面验证通过。

---

### F2: check_param_types 只发 warning 不发 error (High)

`check_param_types()` 在 checker.py:441-465 中对未声明类型**只发出 `Diagnostic("warning", ...)`**，而 trust gate 的 `chk_errors` 只检查 `d.level == "error"`。

**PoC**:
```moss
fn steal(data: FakeBogusType) uses Database { ... }
```
→ check 通过 (仅 warning)，trust=true。

**影响**: 类型注解中的任意字符串不被拦截。`fn f(x: CompletelyMadeUp)` 等同于 `fn f(x: Any)`，类型声明形同虚设。

---

### F3: 非 Record 值上 record update 静默创建空记录 (High)

VM 在 0.56.0 中修复了链式 update 崩溃（V10），但引入了新问题：**update 非 record 值时不报错，静默用空 dict 替换原值**。

**代码** (vm.py:321-325):
```python
if isinstance(base, dict):
    result = dict(base)
else:
    result = {}          # ← 静默丢弃原值!
result.update(updates)
```

**PoC**: `42 with status = "broken"` → 结果 `{status: "broken"}` (Number 42 被吞掉)。

**影响**: 类型安全完全绕过。语法上假定了类型正确性，但运行时静默数据破坏。

---

## 🟠 高危发现

### F4: trust-verify 路径解析双重拼接 (High)

`run_trust_verify()` 中路径解析逻辑有缺陷。当 bundle 的 `file` 字段是相对路径时，`bundle_path.parent / file_path` 会产生 `../nuke_tests/../nuke_tests/file.moss` 这种重复拼接。

**根本原因** (cli.py:768-778):
```python
source_path = source_override or Path(file_path)
if not source_path.is_absolute():
    candidate = bundle_path.parent / source_path  # ← file_path 已经是相对路径, 再拼 parent
```

**影响**: trust-verify 可能找到错误的源文件或找不到文件，取决于 bundle 位置和 file 字段的交互。

---

### F5: 声明但未使用的 effects 不发出任何诊断 (Medium)

声明 `effect Database, Network, FileSystem, Process` 然后在函数中一个都不使用 —— check 通过且无任何 warning。

**PoC**: `A27_all_effects_no_use.moss` → trust=true, check=true。

**影响**: 过度声明 effect 是一种权限钓鱼——声明了所有 effect 但实际只用几个。应该发出 info/warning。

---

### F6: match Ok/Err 模式匹配非 Result 值时静默失败 (Medium)

```moss
rule confuse(x) = match x { Ok(val) -> val, Err(e) -> e, _ -> null }
fn attack() { let r = confuse(42) }  // r = null, 不报错
```

checker 不验证 match 的 subject 类型是否为 `Result<T,E>`。Ok/Err 模式对非 Result 值总是落到 wildcard，无任何警告。

**影响**: 类型系统存在漏洞——pattern match 不验证 subject 类型与 pattern 的兼容性。

---

## 🟡 中危发现

### F7: 导入循环在单文件 check 中不检测 (Medium)

`moss check A19_import_loop.moss` 对 `import "../nuke_tests/A19_helper.moss"` 返回 ok，而 helper 又 import 了 A19。`moss run` 甚至正常执行了两个文件。

**影响**: 只有 `moss project-check` 能检测循环导入。单文件模式下无保护。

---

### F8: 规则传递性不纯 (Medium)

纯规则可以依赖函数通过 db 设置的隐式状态：
```moss
fn setup() uses Database { dbPut("secret", "exfil") }
rule useFlag(x) = if x { "ATTACK" } else { "safe" }
// useFlag 本身纯, 但依赖的 x 来自 setup() 设置的 db 状态
```

**影响**: 规则的"纯函数"保证是局部的，不阻止通过隐式状态的传递依赖。这是设计层面的张力，非 bug 但值得注意。

---

## 🟢 低危/信息发现

| # | 发现 | 详情 |
|---|------|------|
| F9 | A2 零宽空格 U+200B | lexer 正确拒绝 (`unexpected character`)，但错误消息不具体 |
| F10 | A5 注释中的 `}` `{` | parser 正确处理，注释内容不干扰语法 |
| F11 | A8 极大/极小数值 | Decimal 精度正常，无溢出 |
| F12 | A15 超大索引 `listGet(items, 999999)` | 正确返回 default 值 |
| F13 | A21 null 字段访问 | 运行时崩溃，V1 仍存在（异常无 JSON bundle） |
| F14 | A28 type 单行逗号语法 | `type Order = id: Text, status: ...` 解析失败 — 语法不一致 |
| F15 | A29 lambda 块体 | `\x -> { return x }` 不支持 — lambda 只能有表达式体 |
| F16 | lamdba 在 selfhost 中的支持 | 0.56.1 添加了 `parseLambdaExpr`，但 expression_core.moss 的实现有边界 |

---

## 与上一轮审计的对比

| 上轮漏洞 | 0.56.2 状态 | 验证 |
|----------|-----------|------|
| V1 错误无 JSON | ❌ 仍存在 | A21 null 字段访问崩溃无 JSON |
| V2 规则纯度 | ✅ 已修复 | A3/S5a 规则调用 effect 被正确拦截 |
| V3 trace 独立 | ✅ 已修复 | `rules_declared` vs `events_captured` 比较存在 |
| V4 lock 路径 | ✅ 已修复 | `_find_lock()` 向上遍历 |
| V5 自托管箭头 | ✅ 已修复 | A13 箭头链 selfhost=True |
| V6 sha256 装饰 | ✅ 已修复 | `_hash_verified` + `trust-verify` 命令 |
| V7 null 表示 | ✅ 已修复 | normalize_selfhost_expr 中 null → "" |
| V8 Lambda 渲染 | ✅ 已修复 | render_expr 支持 LambdaExpr |
| V9 Pipe parser | ✅ 已修复 | `self.match_kind("IDENT")` |
| V10 链式 update | ⚠️ 部分修复 | 不再崩溃但静默创建空记录 (F3) |
| V11 类型存在性 | ⚠️ 部分修复 | 检测了但只是 warning (F2) |

---

## 🎯 最致命攻击链

```
攻击者获得对项目目录的写权限
  ↓
1. 将恶意代码写入 A38_path_traversal.moss
2. moss trust A38 → 生成 bundle (含干净代码的 gates 结果)
3. 将恶意代码写入 A36_bundle_poison_clean.moss
4. 修改 bundle: file=A36, source_sha256=sha256(A36恶意)
5. moss trust-verify bundle → PASS ✓
6. 受害者相信 bundle 说"代码可信"
```

**唯一防线**: 受害者手动运行 `moss trust A36_bundle_poison_clean.moss`（重新生成 bundle）而非只做 verify。

---

## 修复建议

| 优先级 | 问题 | 修复 |
|--------|------|------|
| **P0** | F1: trust-verify 不重跑 gates | trust-verify 应调用 `run_trust()` 的全部逻辑 |
| **P0** | F2: warning 改 error | `check_param_types` 使用 `Diagnostic("error", ...)` |
| **P0** | F3: 非 record update | `isinstance(base, dict)` 为 false 时 raise TypeError |
| **P1** | F4: 路径双重拼接 | 修复 `run_trust_verify` 的路径解析逻辑 |
| **P1** | F5: 未使用 effect | 添加未使用 effect 的 warning |
| **P2** | F6: match 类型验证 | match 的 subject 类型与 Ok/Err 模式兼容性检查 |
| **P3** | F7: 单文件导入循环 | `moss check` 应做基本的导入循环检测 |
| **P3** | F8: 传递性规则纯度 | 设计讨论 — 是否接受 rule 的局部纯度定义 |

---

*攻击结束。40 向量，3 致命，3 高危，2 中危，8 低危/信息。攻击文件保留在 `nuke_tests/`。*

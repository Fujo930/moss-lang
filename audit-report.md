# Moss Trust Artifact 管线 — 独立审计报告 (修订版 v2)

**审计对象**: Moss `ds-Mosslang` v0.54 分支  
**审计范围**: `moss trust` / `moss trust-project` 信任管线  
**审计日期**: 2025-07-16  
**审计方法**: 两轮对抗性测试 (16+ 基础用例 + 15+ 饱和攻击)

---

## 执行摘要

Moss 信任管线设计方向正确。两轮审计共计 30+ 测试用例，系统性地覆盖了全部 5 个 gate 的防护边界。与第一轮审计相比，本轮发现了**该分支已修复 3 个原始漏洞** (V2 规则纯度、V3 trace 独立验证、V4 lock 路径搜索)，并在此基础之上新发现 **6 个有效漏洞**。

---

## 🔄 第一轮漏洞纠偏

| 原漏洞 | 原始评估 | 第二轮验证 | 当前状态 |
|--------|----------|-----------|----------|
| V1: 语法/运行时错误不产生 JSON | Medium | ✅ 仍存在 | **有效** |
| V2: Rule 可静默调用 effect 内置函数 | High | ❌ 已修复 (check_rule_effect_calls) | **无效** |
| V3: trace.ok 从不会独立为 False | Low | ❌ 已修复 (独立验证 rules_declared vs events) | **无效** |
| V4: moss trust 找不到 lock 文件 | Medium | ❌ 已修复 (_find_lock 向上搜索) | **无效** |
| V5: 自托管箭头函数体边界错误 | High | ✅ 仍存在 | **有效** |
| V6: source_sha256 仅装饰性存储 | Low | ✅ 仍存在 | **有效** |

---

## 第二轮测试结果全景

### S1: 外部路径攻击

| # | 测试 | trust | 发现 |
|---|------|-------|------|
| S1a | 项目外文件 (null literal) | False | **V7**: 自托管 null 表示为 `"null"` vs host `""` |
| S1b | 深层嵌套路径 | True | 路径规范化正常 |
| S1c | Unicode 路径 | N/A | GBK 编码问题 (Windows 终端) |

### S2: 编码/空白/边界攻击

| # | 测试 | trust | 发现 |
|---|------|-------|------|
| S2b | Tab 缩进 | True | Tab 缩进完全兼容 |
| S2c | 超长标识符 (~400 chars) | True | 词法/解析无异常 |

### S3: Golden gate 饱和攻击

| # | 测试 | trust | 发现 |
|---|------|-------|------|
| S3a | 换行差异 | False | ✅ Golden 对单字符差异敏感 |
| S3b | 前缀不匹配 | False | ✅ 严格全字符串比较 |
| S3c | Map 输出 (确定性) | True | ✅ 输出在当前实现中确定 |

### S4: Selfhost 深度差异攻击

| # | 测试 | trust | 发现 |
|---|------|-------|------|
| S4a | Lambda 表达式 `\x -> x*2` | **N/A** | **V8**: `render_expr` 不支持 LambdaExpr → selfhost 崩溃 |
| S4b | 管道操作符 `x \|> double` | **N/A** | **V9**: `self.match("IDENT")` 方法不存在 → parser 崩溃 |
| S4c | 链式 record update `with` | **N/A** | **V10**: VM `UnboundLocalError` → 运行时崩溃 |
| S4d | 嵌套 match + Ok/Err | True | ✅ 复杂 match 通过 |
| S4e | 字符串插值 `` `{name}` `` | False | ⚠️ 自托管解析差异 |
| S4f | Empty rule body | False | ⚠️ trace 事件不足 |

### S5: 复合漏洞链攻击

| # | 测试 | trust | 发现 |
|---|------|-------|------|
| S5a | Rule impurity + no golden + no lock | **False** | ✅ V2 已修复，规则纯度被正确检测 |
| S5b | Dead effect code | True | ℹ️ 设计如此 (代码有效，只是未调用) |
| S5c | 递归规则 | True | ℹ️ 正常行为 |
| S5d | 规则通过隐式状态 | True | ℹ️ 规则本身是纯函数，设计正确 |
| S5e | Money 字面量规则未调用 | **False** | ✅ trace 独立验证正确拒绝 |
| S5f | 未声明类型参数 | **True** | **🔴 V11**: 检查器不验证类型存在性 |
| S5g | Null in rule args | False | V7 再次确认 |

---

## 最终漏洞列表 (修订版)

### 🔴 V1 — Parse/Runtime 错误不产生 JSON Bundle (Medium) — 仍有效

**文件**: `src/mosslang/cli.py`, `run_trust()` 函数

**描述**: 当 Moss 源代码有**语法错误**或执行期间发生**运行时错误**（LambdaExpr render、pipe parser bug、VM UnboundLocalError），`moss trust` 不产生 JSON bundle。V8/V9/V10 都是此漏洞的实例。

**PoC 实例**:
- `\x -> x * 2` (LambdaExpr → `TypeError: cannot render LambdaExpr`)
- `x |> double |> addOne` (pipe → `AttributeError: 'Parser' object has no attribute 'match'`)
- `r with a = 1 with b = "!"` (chain update → `UnboundLocalError`)

**影响**: 自动化工具有序消费 trust bundle 的能力被破坏。

---

### 🔴 V5 — 自托管箭头函数体边界错误 (High) — 仍有效

**文件**: `examples/self_host/parser_core.moss`

**PoC**: `fn f() = 42\nfn g() { print("g") }\ng()\nf()\n` → selfhost 将 `g()` 也吞入 `f` 的函数体

**影响**: 箭头函数后跟随任何顶级声明 (fn/let/type) 都会导致 selfhost 不等价。

---

### 🔴 V7 — Selfhost null 表示差异 (Medium) — 新发现

**文件**: `src/mosslang/cli.py`, `normalize_host_expr()` vs `normalize_selfhost_expr()`

**描述**: Host `('Null', '')` vs selfhost `('Null', 'null')` — null 字面量的内部表示不同。

**PoC**: 任何使用 `null` 字面量的 Moss 文件，从项目外运行 `moss trust` 时，expression AST 比较失败。

**影响**: 从项目外运行时，含 null 的表达式导致 selfhost gate 误判。

---

### 🔴 V8 — LambdaExpr 渲染崩溃 (Medium) — 新发现

**文件**: `src/mosslang/cli.py`, `render_expr()` 函数

**描述**: `render_expr()` 方法缺少 `LambdaExpr` 分支，导致 `TypeError: cannot render LambdaExpr`。

**PoC**: 任何包含 `\x -> expr` 的 .moss 文件

**影响**: Lambda 是语言规范中的正式特性，但 trust 管道不兼容。

---

### 🔴 V9 — Pipe 操作符 parser bug (Medium) — 新发现

**文件**: `src/mosslang/parser.py`, `parse_update()` 349 行

**描述**: `self.match("IDENT")` 方法不存在。正确方法应为 `self.check("IDENT")` 或 `self.match_kind("IDENT")`。

**PoC**: `x |> double |> addOne`

**影响**: Pipe 操作符是语言正式特性但实际崩溃。

---

### 🔴 V10 — 链式 record update VM 崩溃 (Medium) — 新发现

**文件**: `src/mosslang/vm.py`, `_execute()` 方法

**描述**: `r with a = r.a + 1 with b = r.b + "!"` → VM 内部 `UnboundLocalError: cannot access local variable 'result'`

**影响**: 链式 record update 是有效语法但运行时崩溃。

---

### 🔴 V11 — 未声明类型参数不被校验 (Medium) — 新发现

**文件**: `src/mosslang/checker.py`

**描述**: `fn process(data: UnknownType) { ... }` — checker 不验证 `UnknownType` 是否是已声明的类型。

**PoC**: 函数参数声明任意类型名而不报错。

**影响**: 类型系统的完整性受损。类型注解成为纯粹的文档。

---

### 🔴 V6 — source_sha256 仅装饰性存储 (Low) — 仍有效

**描述**: Bundle 中的 SHA-256 哈希未做消费端验证。

---

## 信任管线真实防护边界 (修订版)

### 能拦住什么

| 攻击向量 | 能否拦截 | 通过哪个 gate |
|----------|----------|--------------|
| 类型不匹配 | ✅ | Check |
| 缺失 effect 声明 | ✅ | Check |
| 使用未声明 effect | ✅ | Check |
| Rule 调用 effect 内置函数 | ✅ | Check (V2 已修复) |
| 重复声明 | ✅ | Check |
| Match 未穷尽 | ✅ | Check |
| Rule 声明但未执行 | ✅ | Trace (V3 已修复) |
| Golden 输出不一致 | ✅ | Golden |
| Lock 文件不匹配 | ✅ | Lock (V4 已修复) |
| 自托管解析不等价 | ⚠️ | Selfhost (有已知 bug) |
| 未声明类型参数 | ❌ V11 | 无 gate 拦截 |

### 不能拦住什么

| 攻击向量 | 能否拦截 | 原因 |
|----------|----------|------|
| Lambda 语法 | ❌ V8 | render_expr 不支持 |
| Pipe 语法 | ❌ V9 | Parser bug |
| 链式 record update | ❌ V10 | VM bug |
| Bundle JSON 不输出 (错误时) | ❌ V1 | 无全局异常保护 |
| Null 表示差异 | ❌ V7 | normalize 不一致 |
| Bundle 完整性验证 | ❌ V6 | source_sha256 装饰性 |
| 类型参数存在性 | ❌ V11 | Checker 不验证 |

---

## 严重性评估 (修订版)

| 漏洞 | 严重性 | 影响 |
|------|--------|------|
| V5: 箭头函数自托管 | **High** | 自托管不等价 (常见模式) |
| V1: 错误不产生 JSON | Medium | 自动化管道断裂 |
| V7: Null 表示差异 | Medium | 自托管误判 |
| V8: Lambda 渲染崩溃 | Medium | 语言特性不可用 |
| V9: Pipe parser bug | Medium | 语言特性不可用 |
| V10: 链式 update VM 崩溃 | Medium | 运行时崩溃 |
| V11: 类型参数不校验 | Medium | 类型系统被绕过 |
| V6: hash 装饰性 | Low | Bundle 完整性无保证 |

---

## 建议修复优先级

1. **P0:** V9 — Pipe parser bug (`self.match` → `self.check`)
2. **P0:** V8 — LambdaExpr 渲染支持
3. **P0:** V10 — VM 链式 record update
4. **P1:** V1 — 全局异常保护
5. **P1:** V5 — 自托管箭头函数解析
6. **P1:** V7 — Null 表示统一
7. **P2:** V11 — 类型参数存在性校验
8. **P3:** V6 — source_sha256 验证

---

## 审计测试文件

### 第一轮 (16 文件)
`moss-fork/audit_tests/`

### 第二轮 (15+ 文件)
`saturation_tests/` (moss-fork 同级目录)

---

*审计结束。两轮共计 30+ 测试，发现 8 个有效漏洞 (3 个已修复，5 个新发现)，数据目录已保留供复现。*

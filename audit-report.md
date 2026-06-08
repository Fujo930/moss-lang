# Moss Trust Artifact 管线 — 独立审计报告

**审计对象**: Moss `ds-Mosslang` v0.54 分支  
**审计范围**: `moss trust` / `moss trust-project` 信任管线  
**审计日期**: 2025-07-16  
**审计方法**: 对抗性测试、边界用例、代码审查

> **修复状态 (v0.55.0)**: 6 个漏洞全部修复 — 见 CHANGELOG.md v0.55.0。

---

## 执行摘要

Moss 信任管线整体设计方向正确。5 个 gate（check / trace / golden / lock / selfhost）各自的功能逻辑基本正确，**常见检查和类型错误均能正确拒绝 trust**。但存在 6 个安全/质量漏洞，其中 1 个 High、3 个 Medium、2 个 Low。

---

## 测试结果全景

| # | 测试场景 | 预期 | 实际 | 状态 |
|---|----------|------|------|------|
| 1 | 基线: order.moss (合法) | trust=true | trust=true | ✅ |
| 2a | 语法错误 (残缺大括号) | trust=false, JSON bundle | trust=false, **无 JSON** | ⚠️ V1 |
| 2b | 类型错误 (传递 Number 给 Order) | trust=false | trust=false | ✅ |
| 2c | 效果缺失 (dbPut 无 uses) | trust=false | trust=false | ✅ |
| 2d | 未声明效果 (uses NonExistentEffect) | trust=false | trust=false | ✅ |
| 2e | 重复声明 | trust=false | trust=false | ✅ |
| 2f | match 未穷尽 | trust=false | trust=false | ✅ |
| 2g | 空文件 | trust=true (无错误) | trust=true | ✅ |
| 2h | 类型注解语法 (let x: T = ...) | N/A (语法不支持) | 解析错误 | ℹ️ 设计如此 |
| **2i** | **规则调用 effect 内置函数** | **trust=false** | **trust=true** | **🔴 V2** |
| 3a | 无 rule 的文件 (空 trace) | trace.ok=true | trace.ok=true | ✅ |
| 3b | 各种返回值类型的 rule | 5 events 正确 | 5 events 正确 | ✅ |
| 3c | 多 rule 调用 | trace 正确捕获 | 正确 (3 events) | ✅ |
| 3d | trace --json vs trust trace | 完全一致 | 完全一致 | ✅ |
| 3e | trace.ok 是否独立失效 | trace.ok 从不独立失效 | 仅当 check 失败才 false | ⚠️ V3 |
| 4a | 无 .golden 文件 | golden.ok=null, trust=true | golden.ok=null, trust=true | ✅ |
| 4b | golden 匹配 | golden.ok=true, trust=true | golden.ok=true, trust=true | ✅ |
| 4c | golden 不匹配 | golden.ok=false, trust=false | golden.ok=false, trust=false | ✅ |
| 5a | 无 moss.lock (独立文件) | lock.ok=null, trust=true | lock.ok=null, trust=true | ✅ |
| **5b** | **文件在项目中但 moss trust 检查单个文件** | **lock 被找到并验证** | **lock.ok=null (找不到)** | **🔴 V4** |
| 5c | source 被篡改后 trust-project | lock.ok=false, trust=false | lock.ok=false, trust=false | ✅ |
| 6a | Unicode 非 ASCII 字符 | selfhost.ok=true | selfhost.ok=false (编码差异) | ⚠️ Low |
| 6b | 简单文件 | selfhost.ok=true | selfhost.ok=true | ✅ |
| 6c | let 绑定文件 | selfhost.ok=true | selfhost.ok=true | ✅ |
| 6d | type + rule 文件 | selfhost.ok=true | selfhost.ok=true | ✅ |
| **6e** | **箭头函数后跟 let 声明** | **selfhost.ok=true** | **selfhost.ok=false** | **🔴 V5** |
| 7a | 复合合法文件 | trust=true | trust=true | ✅ |
| 7b | Rule impurity + runtime error | trust=false (有 JSON) | **无 JSON** | ⚠️ V1 扩展 |

---

## 漏洞详情

### 🔴 V1 — Parse / Runtime 错误不产生 JSON Bundle (Medium)

**文件**: `src/mosslang/cli.py`, `run_trust()` 函数 (741-876 行)

**描述**: 当 Moss 源代码有**语法错误**或执行期间发生**运行时错误**（如 ZeroDivisionError、文件不存在异常等），`moss trust` 不会产生任何 JSON bundle。错误信息仅输出到 stderr，stdout 完全为空，进程以 exit code 1 退出。

**根本原因**: `run_trust()` 函数中所有的 parse/compile/execute 步骤都没有被 try/except 包裹。异常传播到 `main()` 函数的最外层 except handler，只捕获 `MossError`（自定义异常），但 `ZeroDivisionError`（Python 内置）、`OSError`（文件操作）等直接导致崩溃。

**代码路径**:
- 第 755 行: `program = parse_source(source)` — 语法错误时抛出 `MossSyntaxError`
- 第 802-805 行: VM 执行 trace 时可能抛出 Python 内建异常
- 第 819-822 行: VM 执行 golden 时可能抛出 Python 内建异常

**影响**: 自动化工具有序消费 trust bundle 的能力被破坏——语法错误和运行时错误场景下只能靠 exit code 判断失败，无法获取结构化的诊断信息。

**建议修复**: 在 `run_trust()` 中用 try/except (BaseException) 包裹整个流程，确保即使出错也能输出包含 `check` 诊断的 JSON bundle。

---

### 🔴 V2 — Rules 可静默调用 Effect 内置函数 (High)

**文件**: `src/mosslang/checker.py`, `check_program()` 函数 (65-94 行)

**描述**: `rule` 声明不能使用 `uses` 子句（语法不允许），但**检查器也没有验证 rule 内部是否调用了 effect 内置函数**。`check_effect_calls()` 只在第 91 行对 `FunctionDecl` 调用，完全跳过了 `RuleDecl`。

**代码路径**:
```python
for item in program.items:
    if isinstance(item, FunctionDecl):       # ← 只检查 FunctionDecl
        for effect in item.uses:
            ...
        check_effect_calls(item, functions, diagnostics)  # ← 不对 rule 检查
```

**PoC**:
```moss
effect Database
rule impureRule(order) =
  dbPut(order.id, order)  // checker 不报错, trust=true
```

**影响**: 严重违反 Moss 的核心语言承诺——`rule` 应当是纯函数、可追踪、无副作用的。允许 rule 静默调用 effect 破坏了 trace 系统的完整性、静态分析的可靠性，以及整个信任模型。

**建议修复**: 
1. 在 `check_program()` 中对 `RuleDecl` 也调用 `check_effect_calls()`
2. 或者：如果 rule 使用了 effect 内置函数，应当报 error

---

### 🔴 V3 — trace.ok 从不会独立为 False (Low)

**文件**: `src/mosslang/cli.py`, `run_trust()` 函数 (800-814 行)

**描述**: `trace.ok` 字段的值完全由 `chk_errors` 决定——check 通过时永远是 `true`，check 失败时永远是 `false`。**不存在 trace 本身被判定为"失败"的场景**，即使 trace 事件不完整、被截断、或 source map 不正确。

**代码路径**:
```python
if not chk_errors:      # ← 唯一条件
    # ... run trace ...
    bundle["trace"] = {"ok": True, "events": [...]}
else:
    bundle["trace"] = {"ok": False, "events": []}  # ← 只因 check 失败
```

**影响**: trace gate 本质上是一个冗余字段，不能提供独立于 check 的验证信号。如果 trace 应该验证 rule 的运行时行为与声明的参数/返回值是否匹配，那么它现在什么都没做。

**建议修复**: 增加 trace 自身的验证逻辑，例如验证 trace events 的数量与声明的 rule 是否一致、参数类型是否匹配等。

---

### 🔴 V4 — `moss trust <file>` 在项目中找不到 lock 文件 (Medium)

**文件**: `src/mosslang/cli.py`, `run_trust()` 函数 (776-776 行)

**描述**: `moss trust` 在检查 lock 文件时只查找 `path.parent / "moss.lock"`。对于项目中子目录下的文件（如 `src/main.moss`），其父目录是 `src/`，而 lock 文件在项目根目录 `./moss.lock`。这导致 lock 验证总是被静默跳过（`lock.ok=null`）。

**代码路径**:
```python
lock_path = path.parent / "moss.lock"    # 只查同目录，不向上遍历
```

**影响**: 即使项目有完整的 `moss.toml` + `moss.lock`，对单个文件运行 `moss trust` 时 lock 验证永远不会生效。唯有 `moss trust-project` 能正确找到 lock。

**建议修复**: 从文件目录向上逐级搜索 `moss.lock`，或使用 `find_manifest()` 找到项目根目录再定位 lock。

---

### 🔴 V5 — Selfhost Parser: 箭头函数体边界错误 (High)

**文件**: `examples/self_host/parser_core.moss` (自托管 Moss 解析器)

**描述**: 使用箭头函数体语法 `fn name(params) = expr` 时，Moss 编写的前端解析器没有正确终止函数体，导致**后续顶级声明被吞并到函数体中**。当箭头函数后跟 `let`、`fn` 等声明时，selfhost 比较一定失败。

**PoC**: 文件 `fn f() = 42\nlet x = 1\n` 中，自托管解析器将 `let x = 1` 视为 `f` 函数体的一部分。

**影响**:
- 所有使用了箭头函数的文件在 selfhost 比较中都会得到 `bodies_match=false`
- 自托管前端与宿主前端之间的解析器不等价
- 箭头函数后跟 `let` 是常见模式，影响面广泛

**建议修复**: 修复 `parser_core.moss` 中箭头函数体解析的逻辑，确保遇到顶级声明关键字时终止函数体。

---

### 🔴 V6 — source_sha256 仅存储但不用于验证 (Low)

**文件**: `src/mosslang/cli.py`, `run_trust()` 函数 (746-750 行)

**描述**: trust bundle 中包含 `source_sha256` 字段，该字段是源代码的 SHA-256 哈希。但该哈希**只在 bundle 中存储，不做任何验证**——没有任何逻辑检查 bundle 的哈希是否与再次读取的源代码匹配。它是"装饰性"字段。

**代码路径**:
```python
source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
bundle["source_sha256"] = source_hash     # 存储但不交叉验证
```

**影响**: 如果 bundle JSON 被篡改或与源代码分离，consumer 无法知道哈希是否真实匹配。

**建议修复**: 添加 bundle 消费端的哈希验证逻辑，或使用签名机制确保 bundle 完整性。

---

## 信任管线的真实防护边界

### 能拦住什么

| 攻击向量 | 能否拦截 | 说明 |
|----------|----------|------|
| 语法错误代码 | ✅ | 但不会产生 JSON bundle (V1) |
| 类型错误 | ✅ | 类型推断正确捕获不匹配 |
| 缺失 effect 声明 | ✅ | 函数级别检查有效 |
| 使用未声明 effect | ✅ | `uses` 子句验证 |
| 重复声明 | ✅ | 类型/函数/规则重复检测 |
| Match 未穷尽 | ✅ | 联合类型覆盖率检查 |
| Golden 输出不一致 | ✅ | 严格字符串比较 |
| Lock 文件不匹配 | ✅ | trust-project 可检测篡改 |
| 自托管解析不等价 | ✅ | 多维度比较 (5 gates) |

### 不能拦住什么 (当前边界)

| 攻击向量 | 能否拦截 | 原因 |
|----------|----------|------|
| Rule 调用 effect 内置函数 | ❌ V2 | Checker 不检查 RuleDecl |
| 单文件 lock 绕过 | ❌ V4 | 不向上搜索 lock 文件 |
| 运行时错误导致 bundle 丢失 | ❌ V1 | 没有全局异常保护 |
| Arrow 函数自托管误判 | ❌ V5 | Parser 边界错误 |
| Bundle 完整性验证 | ❌ V6 | source_sha256 仅装饰 |

---

## 严重性评估

| 漏洞 | 严重性 | 利用难度 | 实际影响 |
|------|--------|----------|----------|
| V1: 错误不产生 JSON | Medium | 低 (任何语法/运行时错误) | 自动化管道断裂 |
| V2: Rule 隐式调用 effect | **High** | 低 | 破坏核心语言保证 |
| V3: trace.ok 冗余 | Low | N/A | 架构设计问题 |
| V4: lock 找不到 | Medium | 低 (任何子目录文件) | 锁验证静默绕过 |
| V5: 箭头函数解析 | **High** | 低 (常见语法模式) | 自托管不一致 |
| V6: hash 装饰性 | Low | 低 | bundle 完整性无保证 |

---

## 建议修复优先级

1. **立即 (P0):** V2 — rule 纯度检查 (影响核心语言保证)
2. **立即 (P0):** V5 — 自托管箭头函数解析 (影响自托管正确性)
3. **高 (P1):** V1 — 异常保护使 JSON bundle 总是输出
4. **高 (P1):** V4 — lock 文件向上搜索
5. **中 (P2):** V6 — source_sha256 消费端验证
6. **低 (P3):** V3 — 使 trace gate 具有独立验证能力

---

## 验证命令摘要

```bash
# 基线
moss trust examples/order.moss

# Check gate 对抗测试
moss trust audit_tests/2b_type_error.moss
moss trust audit_tests/2c_missing_effect.moss
moss trust audit_tests/2d_undeclared_effect.moss
moss trust audit_tests/2e_duplicate.moss
moss trust audit_tests/2f_match_not_exhaustive.moss

# 漏洞复现
moss trust audit_tests/2i_effect_in_rule.moss  # V2: trust=true (应为 false)

# Trace 一致性
moss trace --json examples/order.moss
diff <(moss trace --json examples/order.moss) <(moss trust examples/order.moss | jq .trace)

# Golden gate
moss golden --update examples/order.moss  # 可被用于欺骗 trust

# Lock gate (项目内)
moss trust-project .

# 自托管比较
moss selfhost-compare examples
```

---

*审计结束。6 个漏洞已记录，其中 2 个 High 严重性。*

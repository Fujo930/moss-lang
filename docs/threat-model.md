# Moss Trust Artifact — 威胁模型

## Trust Artifact 是什么

`moss trust` 产出一个机器可读的 JSON bundle，包含五个独立维度的验证结果：

| Gate | 验证内容 | 所信神谕 |
|------|---------|---------|
| **check** | 静态分析：类型、effect、match 穷尽性 | Python 宿主 checker |
| **trace** | 规则求值：运行时记录每个 `rule` 的调用 | VM 的 trace 机制 |
| **golden** | 输出快照：确定性输出匹配 `.golden` 文件 | `.golden` 文件 |
| **lock** | 依赖完整性：导入图哈希匹配 `moss.lock` | `moss.lock` 文件 |
| **selfhost** | 编译器完整性：Moss 解析器 ↔ Python 解析器等价 | `parser_core.moss` |

五个 gate 同时通过，意味着这五个神谕各自独立地没有发现问题。

**Trust Artifact 是结构化信任证据 (structured evidence)，不是形式化证明 (proof)。**

---

## Trust 能防什么

### 代码完整性 (Integrity)

Trust 管线检测**意图和结果之间的偏差**：

- 你声明了 `uses Database` 却没声明 `effect Database` → check gate 拒绝
- 你声明了 `rule canShip` 是纯函数，却调用了 `dbPut` → check gate 拒绝
- 你依赖了某模块，该模块的哈希发生了变化 → lock gate 拒绝
- 你的代码输出和 golden 快照不一致 → golden gate 拒绝
- Moss 自宿主解析器对同一段代码的理解和 Python 宿主不同 → selfhost gate 拒绝

这些全是在检测**代码变了但验证没跟上的情况**。

### 复合防御

单个 gate 各自可被绕过，但五个正交 gate **同时**被绕过需要同时欺骗五个独立子系统。这是 Trust 的核心价值：不是每个 gate 多强，是它们的独立性。

---

## Trust 不能防什么

### 代码本身就是恶意的

```moss
effect FileSystem

fn steal(path) uses FileSystem {
  print(readText(path))
}
steal("/etc/passwd")
```

这段代码：effect 声明正确 ✅、类型检查通过 ✅、没有 rule 违规 ✅、自托管等价 ✅。Trust 管线验证的是**代码做了它说的事**，不是**它说的事是对的**。

### 神谕本身被篡改

如果攻击者控制了 Trust 管线依赖的组件：

- 替换了 Python checker → check gate 不可信
- 替换了 VM → trace gate 不可信
- 替换了 golden 文件 → golden gate 不可信
- 替换了 `parser_core.moss` → selfhost gate 不可信

Trust Artifact 的验证能力受限于它的可信计算基 (TCB)：**Python 运行时 + mosslang 包 + 自宿主模块 + golden/lock 文件**。

---

## 自托管悖论

Moss 的 selfhost gate 比较两个解析器的输出：Python 宿主解析器和用 Moss 写的自托管解析器。如果两者一致→增信；不一致→怀疑。

但这里有一个递归信任问题：

```
谁写了待验证的 Moss 代码？    → 可能是 AI
谁写了 parser_core.moss？      → 也可能是同一个 AI
```

如果一个 AI 同时写了恶意代码和"看起来在验证它但其实放过了它"的自托管解析器，两个神谕的证词都不会揭示问题。

这是**所有自托管系统共享的递归信任问题**。Moss 没有制造它，只是把它暴露得比其他语言更尖锐——因为 Moss 的设计目标就是"人类和 AI 在同一个代码库上工作"。当 AI 可以同时写代码和写编译器时，基于编译器的验证就丢失了独立性。

### 消费者的防线

对于需要独立验证的消费者：

- selfhost gate 提供的是**相对于自托管解析器的正确性**，不是绝对正确性
- 如果自托管解析器的完整性存疑，可以只信任 check + trace + golden + lock 四个 gate
- 终极防线是**独立重跑**：消费者用自己的环境重新执行 `moss trust`，不信任生产者提供的 bundle

---

## F1：信任 Bundle 的密码学边界

`moss trust-verify` 命令验证一个 bundle JSON 是否和源代码一致。它的工作方式是：

1. 读取 bundle 中的 `file` 字段找到源文件
2. 重新计算源文件的 SHA-256
3. 重新执行全部五个 gate
4. 比较运行结果与 bundle 中存储的结果

### 为什么不对 file 字段签名

Trust bundle 是一个 JSON 文件，`file` 字段是普通字符串。bundle 本身没有被签名——没有任何密码学机制阻止攻击者修改 `file` 字段指向另一个文件。

这是**设计选择**，不是遗漏。理由：

- 签名需要一个密钥管理基础设施，这在 Moss 的当前架构范围之外
- Token 签名不能解决根本问题：如果攻击者控制磁盘，他们可以同时修改源文件、bundle、甚至签名验证器本身
- 实用的防线比密码学更直接：**消费者显式指定 `--source`** 绕过 bundle 的 `file` 字段

### 消费者的三条防线

1. **显式来源**：`moss trust-verify --source /path/to/expected/file.moss bundle.json` — `--source` 覆盖 bundle 的 `file` 字段
2. **检查跳转标记**：如果 bundle 的 `file` 和实际解析的源文件路径不一致，输出中 `file_redirected` 为 `true`
3. **独立生成**：不信任任何 bundle，自己运行 `moss trust file.moss` 重新生成

---

## --strict 模式

默认情况下，以下诊断级别为 **warning**，不翻转 `trust`：

- **F5**: 声明但未使用的 effect
- **F6**: 非 Result 类型上使用 Ok/Err match 模式
- **F7**: 可能的导入循环

这些是"可疑但不阻止"的诊断。在宽松模式（默认）下，它们作为信息输出；在 `--strict` 模式下，它们被提升为 error 并翻转 `trust`。

选择宽松默认的理由：F5/F6/F7 在合法的 Moss 代码中可能出现——特别是自宿主代码，它们跨文件引用类型、声明模块级 effects 但单函数不全部使用。将这些升级为 error 会破坏合法项目的 trust 结果。

### 行为

| 模式 | `moss trust` | `moss trust-verify` |
|------|-------------|---------------------|
| 默认 | warnings 不影响 trust | warnings 不影响 verified |
| `--strict` | warnings → errors → trust=false | warnings → errors → verified=false |

---

## 信任级联图

```
你的代码 (.moss)
    │
    ├─→ Python checker ──────→ check gate   ─┐
    ├─→ VM trace ─────────────→ trace gate   ─┤
    ├─→ VM output ────────────→ golden gate  ─┼─→ trust bundle
    ├─→ lock 文件 ────────────→ lock gate    ─┤    (structured
    └─→ parser_core.moss ─────→ selfhost gate─┘     evidence)
         ▲
         │ "用 Moss 写的解析器验证 Moss 代码"
         │  写解析器的 AI 和写代码的 AI 可以是同一个
```

箭头往下流动的是验证。往上看的是信任——每一层都假定下一层未被篡改。

---

## 版本历史

| 版本 | 变更 |
|------|------|
| 0.57 | 初始威胁模型。F1-F7 发现后的边界文档化。 |

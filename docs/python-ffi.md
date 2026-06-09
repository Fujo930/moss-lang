# Moss Python FFI — 外部函数接口

**版本**: alpha0.8  
**状态**: Alpha — Python VM 可用，C VM 待实现

---

## 概述

Moss 通过 `extern "python"` 语法调用 Python 生态中的任何库。

```moss
extern "python" fn sqrt(x: Number) -> Number = "math.sqrt"
let x = sqrt(42)  // 调用 Python 的 math.sqrt(42)
```

## 语法

```moss
extern <lang> fn <name>(<params>) -> <return_type> = "<target>"
```

| 部分 | 说明 |
|------|------|
| `extern` | 关键字 |
| `<lang>` | 当前仅支持 `"python"` |
| `fn <name>` | 在 Moss 中使用的函数名 |
| `<params>` | 参数列表（名称和可选类型） |
| `-> <return_type>` | 可选，声明返回类型 |
| `= "<target>"` | Python 模块名.函数名 |

## 标准绑定包

### moss/math (`stdlib/moss/math.moss`)

```moss
import "stdlib/moss/math.moss"

sqrt(25)   // → 5.0
cos(0)     // → 1.0
sin(1.57)  // → 1.0
pow(2, 10) // → 1024.0
log(1)     // → 0.0
ceil(3.1)  // → 4.0
floor(3.9) // → 3.0
pi()       // → 3.1415...
```

### moss/json (`stdlib/moss/json.moss`)

```moss
import "stdlib/moss/json.moss"

let data = jsonLoads("{\"a\": 1}")
let text = jsonDumps(data)
```

### moss/http (`stdlib/moss/http.moss`)

```moss
import "stdlib/moss/http.moss"

let html = urlOpen("https://example.com")
```

## 类型转换

Moss 和 Python 之间的类型自动转换：

| Moss → Python | Python → Moss |
|---------------|---------------|
| `None` → `None` | `None` → `null` |
| `Number` → `Decimal` → `float` | `int/float` → `Decimal` |
| `Bool` → `bool` | `bool` → `Bool` |
| `Text` → `str` | `str` → `Text` |
| `List` → `list` | `list/tuple` → `List` |
| `Record` → `dict` | `dict` → `Record` |
| `Variant` → `str` | — |
| `Money` → `float` | — |

## 限制 (Alpha)

| 限制 | 计划 |
|------|------|
| C VM 不支持 (返回 null) | alpha0.9+ |
| 无关键字参数 | alpha0.9+ |
| 无 `extern "c"` | v1.0+ |
| 类型检查不验证 extern | design choice |
| Selfhost parser 部分支持 | alpha0.9+ |

## 架构

```
Moss 源码
  → Parser: extern "python" fn → PythonExternDecl 节点
  → Checker: 注册为 callable，跳类型检查
  → Compiler: LOAD_CONST(target) + STORE_GLOBAL(name)
  → VM import: 导入的 extern 注册为 globals["name"] = "mod.fn"
  → VM call: _resolve_callable → 识别带点的字符串 → _do_call_python_str
  → dispatch: importlib.import_module + getattr + fn(*args)
```

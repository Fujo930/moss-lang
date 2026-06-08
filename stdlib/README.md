# Moss Standard Library (v0.20+)

## collections.moss
```moss
fn map(ls, fn) {
  result = []
  for item in ls { result = listPush(result, fn(item)) }
  return result
}

fn filter(ls, pred) {
  result = []
  for item in ls { if pred(item) { result = listPush(result, item) } }
  return result
}

fn fold(ls, init, fn) {
  acc = init
  for item in ls { acc = fn(acc, item) }
  return acc
}

fn flatten(ls) {
  result = []
  for item in ls {
    for sub in item { result = listPush(result, sub) }
  }
  return result
}
```

## math.moss
```moss
rule abs(n: Number) -> Number = if n < 0 { -n } else { n }
rule min(a: Number, b: Number) -> Number = if a < b { a } else { b }
rule max(a: Number, b: Number) -> Number = if a > b { a } else { b }
rule clamp(v: Number, lo: Number, hi: Number) -> Number = min(max(v, lo), hi)
```

## text.moss
```moss
fn startsWith(s: Text, prefix: Text) -> Bool = textStartsWith(s, prefix)
fn endsWith(s: Text, suffix: Text) -> Bool = textEndsWith(s, suffix)
fn contains(s: Text, sub: Text) -> Bool = textContains(s, sub)
fn repeat(s: Text, n: Number) -> Text {
  result = ""
  for _ in range(0, n) { result = result + s }
  return result
}
fn padLeft(s: Text, width: Number, ch: Text) -> Text {
  if len(s) >= width { return s }
  return textJoin("", [repeat(ch, width - len(s)), s])
}
```

## result.moss
```moss
type Result<T, E> = Ok(T) | Err(E)

fn isOk(r: Result<T, E>) -> Bool = match r { Ok(_) -> true, Err(_) -> false }
fn isErr(r: Result<T, E>) -> Bool = match r { Ok(_) -> false, Err(_) -> true }
fn unwrap(r: Result<T, E>) -> T = match r { Ok(v) -> v }
fn unwrapOr(r: Result<T, E>, default: T) -> T = match r { Ok(v) -> v, Err(_) -> default }
```

## http.moss (requires Network effect)
```moss
fn fetchJson(url: Text) -> Any uses Network {
  body = httpGet(url)
  return jsonParse(body)
}

fn postJson(url: Text, data: Any) -> Any uses Network {
  body = httpPostJson(url, data)
  return if body == "" { null } else { jsonParse(body) }
}
```

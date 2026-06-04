from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from mosslang.checker import check_program
from mosslang.errors import MossRuntimeError
from mosslang.parser import parse_source
from mosslang.runtime import Runtime
from mosslang.studio import analyze_source
from mosslang.values import Result, Variant


class MossLanguageTests(unittest.TestCase):
    def run_source(self, source: str) -> tuple[Runtime, list[str]]:
        output: list[str] = []
        runtime = Runtime(output.append)
        runtime.run(parse_source(source))
        return runtime, output

    def test_order_example_ships_and_stores(self) -> None:
        source = """
effect Database

rule canShip(order) =
  order.status == Paid and order.total > 0.usd

fn ship(order) -> Result<Order, ShipError> uses Database {
  require canShip(order)
    else ShipError.NotReady(order.status)

  updated = order with status = Shipped
  dbPut(order.id, updated)
  return Ok(updated)
}

let order = { id: "A-100", status: Paid, total: 42.usd }
let shipped = ship(order)?
print(shipped.status)
print(dbGet("A-100").status)
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["Shipped", "Shipped"])

    def test_require_returns_err_from_result_function(self) -> None:
        source = """
fn ship(order) -> Result<Order, ShipError> {
  require order.status == Paid
    else ShipError.NotReady(order.status)
  return Ok(order)
}

let order = { id: "A-101", status: Pending }
let result = ship(order)
print(result)
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["Err(ShipError.NotReady(Pending))"])

    def test_missing_database_effect_is_checked(self) -> None:
        program = parse_source(
            """
effect Database

fn save(order) {
  dbPut(order.id, order)
}
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("does not declare uses Database" in d.message for d in diagnostics))

    def test_missing_database_effect_fails_at_runtime(self) -> None:
        source = """
effect Database

fn save(order) {
  dbPut(order.id, order)
}

let order = { id: "A-102", status: Paid }
save(order)
"""
        with self.assertRaisesRegex(MossRuntimeError, "requires effect Database"):
            self.run_source(source)

    def test_try_propagates_err(self) -> None:
        source = """
fn fail() -> Result<Text, Text> {
  return Err("nope")
}

fn outer() -> Result<Text, Text> {
  value = fail()?
  return Ok(value)
}

let result = outer()
"""
        runtime, _ = self.run_source(source)
        result = runtime.globals.get("result")
        self.assertIsInstance(result, Result)
        self.assertFalse(result.ok)
        self.assertEqual(result.value, "nope")

    def test_variant_payload(self) -> None:
        _, output = self.run_source(
            """
let err = ShipError.NotReady(Pending)
print(err)
"""
        )
        self.assertEqual(output, ["ShipError.NotReady(Pending)"])

    def test_record_parameter_type_is_checked(self) -> None:
        source = """
type Order =
  id: Text
  status: Paid | Pending

fn accept(order: Order) -> Text {
  return order.id
}

let bad = { id: 42, status: Paid }
accept(bad)
"""
        with self.assertRaisesRegex(MossRuntimeError, "expected Order"):
            self.run_source(source)

    def test_match_expression_matches_result_payloads(self) -> None:
        source = """
fn ship(status) -> Result<Text, ShipError> {
  require status == Paid
    else ShipError.NotReady(status)
  return Ok("shipped")
}

rule explain(result) =
  match result {
    Ok(message) -> message
    Err(ShipError.NotReady(status)) -> "not ready: " + status
    _ -> "unknown"
  }

print(explain(ship(Pending)))
print(explain(ship(Paid)))
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["not ready: Pending", "shipped"])

    def test_studio_analysis_runs_source(self) -> None:
        result = analyze_source('print("hello studio")', execute=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["output"], ["hello studio"])
        self.assertEqual(result["summary"], {"effects": 0, "imports": 0, "types": 0, "callables": 0, "tests": 0})

    def test_language_test_blocks_run_after_setup(self) -> None:
        source = """
fn ship(order) -> Result<Order, ShipError> {
  require order.status == Paid
    else ShipError.NotReady(order.status)
  return Ok(order with status = Shipped)
}

let order = { id: "A-500", status: Paid }

test "ships paid order" {
  shipped = ship(order)?
  assert(shipped.status == Shipped, "expected shipped")
}
"""
        runtime = Runtime()
        results = runtime.run_tests(parse_source(source))
        self.assertEqual(results, [{"name": "ships paid order", "status": "pass", "message": ""}])

    def test_studio_analysis_runs_tests(self) -> None:
        result = analyze_source(
            """
test "truth" {
  assert(true, "truth should pass")
}
""",
            execute=True,
            test=True,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["output"], ["PASS truth", "1/1 tests passed"])

    def test_lists_for_loops_and_indexing(self) -> None:
        source = """
fn joinWords(words: List<Text>) -> Text {
  result = ""
  for word in words {
    result = result + word
  }
  return result
}

let letters = ["m", "o", "s", "s"]
let built = []
for value in range(1, 4) {
  built = listPush(built, value)
}

print(joinWords(letters))
print(letters[1])
print(len(built))
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["moss", "o", "3"])

    def test_list_type_contract_is_checked(self) -> None:
        source = """
fn countText(words: List<Text>) -> Number {
  return len(words)
}

countText(["ok", 2])
"""
        with self.assertRaisesRegex(MossRuntimeError, "expected List<Text>"):
            self.run_source(source)

    def test_while_break_continue_and_text_helpers(self) -> None:
        source = """
fn takeBeforeColon(text: Text) -> Text {
  chars = textChars(text)
  index = 0
  result = ""
  while index < len(chars) {
    char = chars[index]
    index = index + 1
    if char == "-" {
      continue
    }
    if char == ":" {
      break
    }
    result = result + char
  }
  return result
}

print(takeBeforeColon("mo-ss:language"))
print(textJoin(textSplit("a,b,c", ","), "|"))
print(textSlice("abcdef", 1, 4))
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["moss", "a|b|c", "bcd"])

    def test_filesystem_effect_and_builtins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.moss"
            path.write_text("one\ntwo\n", encoding="utf-8")
            escaped_path = str(path).replace("\\", "\\\\")
            source = f'''
effect FileSystem

fn load(path: Text) -> Result<Text, Text> uses FileSystem {{
  return Ok(readText(path))
}}

let path = "{escaped_path}"
print(textTrim(load(path)?))
print(fileExists(path))
'''
            _, output = self.run_source(source)
        self.assertEqual(output, ["one\ntwo", "true"])

    def test_filesystem_effect_is_checked(self) -> None:
        program = parse_source(
            """
effect FileSystem

fn load(path: Text) -> Text {
  return readText(path)
}
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("does not declare uses FileSystem" in d.message for d in diagnostics))

    def test_map_builtins_and_type_contract(self) -> None:
        source = """
fn wordCounts(words: List<Text>) -> Map<Text, Number> {
  counts = mapNew()
  for word in words {
    counts = mapPut(counts, word, mapGet(counts, word, 0) + 1)
  }
  return counts
}

let counts = wordCounts(["moss", "writes", "moss"])
print(mapGet(counts, "moss"))
print(mapHas(counts, "writes"))
print(len(mapKeys(counts)))
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["2", "true", "2"])

    def test_map_type_contract_is_checked(self) -> None:
        source = """
fn accept(counts: Map<Text, Number>) -> Number {
  return len(counts)
}

bad = mapPut(mapNew(), "moss", "two")
accept(bad)
"""
        with self.assertRaisesRegex(MossRuntimeError, "expected Map<Text, Number>"):
            self.run_source(source)

    def test_imports_load_moss_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "words.moss").write_text(
                """
fn shout(text: Text) -> Text {
  return text + "!"
}
""",
                encoding="utf-8",
            )
            program = parse_source(
                """
import "words.moss"

print(shout("moss"))
"""
            )
            output: list[str] = []
            Runtime(output.append, base_path=root).run(program)
        self.assertEqual(output, ["moss!"])


if __name__ == "__main__":
    unittest.main()

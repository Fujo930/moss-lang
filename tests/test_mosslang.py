from __future__ import annotations

import unittest
import tempfile
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from mosslang.checker import check_program
from mosslang.cli import main as cli_main
from mosslang.errors import MossRuntimeError
from mosslang.formatter import format_source
from mosslang.parser import parse_source
from mosslang.runtime import Runtime
from mosslang.studio import analyze_source, resolve_workspace_path, workspace_root
from mosslang.values import Result, Variant


class MossLanguageTests(unittest.TestCase):
    def run_source(self, source: str) -> tuple[Runtime, list[str]]:
        output: list[str] = []
        runtime = Runtime(output.append)
        runtime.run(parse_source(source))
        return runtime, output

    def test_cli_selfhost_runs_sketches(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["selfhost", "--quick"])
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("PASS examples\\self_host\\tokenizer_sketch.moss", text.replace("/", "\\"))
        self.assertIn("PASS examples\\self_host\\expression_sketch.moss", text.replace("/", "\\"))
        self.assertIn("PASS examples\\self_host\\statement_sketch.moss", text.replace("/", "\\"))
        self.assertIn("PASS examples\\self_host\\parser_sketch.moss", text.replace("/", "\\"))
        self.assertIn("PASS examples\\self_host\\checker_sketch.moss", text.replace("/", "\\"))

    def test_cli_selfhost_compare_matches_order_example(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["selfhost-compare", "examples/order.moss"])
        self.assertEqual(code, 0)
        self.assertIn("selfhost comparison passed", output.getvalue())

    def test_cli_selfhost_compare_matches_examples(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["selfhost-compare", "examples"])
        self.assertEqual(code, 0)
        self.assertIn("examples\\match_demo.moss", output.getvalue().replace("/", "\\"))

    def test_cli_check_json_emits_structured_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.moss"
            path.write_text("fn broken() uses Missing {\n  return 1\n}\n", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = cli_main(["check", "--json", str(path)])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["diagnostics"][0]["line"], 1)
        self.assertEqual(payload["summary"]["callables"], 1)

    def test_cli_check_json_reports_syntax_locations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.moss"
            path.write_text("fn broken( {\n", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = cli_main(["check", "--json", str(path)])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["diagnostics"][0]["line"], 1)
        self.assertIsNone(payload["summary"])

    def test_cli_selfhost_compare_checks_recursive_body_structure(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["selfhost-compare", "examples/text_fs_demo.moss"])
        self.assertEqual(code, 0)
        self.assertNotIn("body-structure comparison failed", output.getvalue())

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
        self.assertEqual(diagnostics[0].location.format(), "4:1")

    def test_studio_diagnostics_include_source_location(self) -> None:
        result = analyze_source("fn broken() uses Missing {\n  return 1\n}\n", execute=False)
        self.assertEqual(result["diagnostics"][0]["line"], 1)
        self.assertEqual(result["diagnostics"][0]["column"], 1)

    def test_formatter_normalizes_indentation_and_preserves_comments(self) -> None:
        source = 'fn work() {\nlet x = "{"   \n# keep me\nif true {\nprint(x)\n}\n}\n\n'
        expected = 'fn work() {\n  let x = "{"\n  # keep me\n  if true {\n    print(x)\n  }\n}\n'
        self.assertEqual(format_source(source), expected)
        self.assertEqual(format_source(expected), expected)
        require_source = "fn work() {\n  require true\n    else Missing\n}\n"
        self.assertEqual(format_source(require_source), require_source)

    def test_cli_format_check_and_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.moss"
            path.write_text("fn work() {\nreturn 1\n}\n", encoding="utf-8")
            self.assertEqual(cli_main(["format", "--check", str(path)]), 1)
            self.assertEqual(cli_main(["format", str(path)]), 0)
            self.assertEqual(cli_main(["format", "--check", str(path)]), 0)

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

    def test_string_escape_sequences(self) -> None:
        runtime, _ = self.run_source(
            """
let newline = "\\n"
let tab = "\\t"
let carriage = "\\r"
let quote = "\\""
let slash = "\\\\"
"""
        )
        self.assertEqual(runtime.globals.get("newline"), "\n")
        self.assertEqual(runtime.globals.get("tab"), "\t")
        self.assertEqual(runtime.globals.get("carriage"), "\r")
        self.assertEqual(runtime.globals.get("quote"), '"')
        self.assertEqual(runtime.globals.get("slash"), "\\")

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

    def test_static_checker_rejects_unknown_record_field(self) -> None:
        program = parse_source(
            """
type Person =
  name: Text

fn greet(person: Person) -> Text {
  return person.missing
}
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("Person has no field 'missing'" in item.message for item in diagnostics))

    def test_static_checker_rejects_record_update_field_type(self) -> None:
        program = parse_source(
            """
type Person =
  name: Text

fn rename(person: Person) -> Person {
  return person with name = 42
}
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("expected Text, got Number" in item.message for item in diagnostics))

    def test_static_checker_tracks_local_assignment_type(self) -> None:
        program = parse_source(
            """
fn work() -> Number {
  total = 1
  total = "wrong"
  return total
}
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("assignment to total" in item.message for item in diagnostics))

    def test_static_checker_checks_call_argument_types(self) -> None:
        program = parse_source(
            """
fn greet(name: Text) -> Text {
  return name
}

fn work() -> Text {
  return greet(42)
}
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("argument name to greet" in item.message for item in diagnostics))

    def test_static_checker_requires_exhaustive_union_match(self) -> None:
        program = parse_source(
            """
type Status = Pending | Paid | Shipped

rule label(status: Status) -> Text =
  match status {
    Pending -> "waiting"
    Paid -> "ready"
  }
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("non-exhaustive match for Status" in item.message for item in diagnostics))

    def test_static_checker_accepts_exhaustive_union_match(self) -> None:
        program = parse_source(
            """
type Status = Pending | Paid

rule label(status: Status) -> Text =
  match status {
    Pending -> "waiting"
    Paid -> "ready"
  }
"""
        )
        diagnostics = check_program(program)
        self.assertFalse(any("non-exhaustive match" in item.message for item in diagnostics))

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

    def test_studio_workspace_paths_stay_inside_repo(self) -> None:
        root = workspace_root().resolve()
        path = resolve_workspace_path("examples/order.moss")
        self.assertEqual(path.relative_to(root).as_posix(), "examples/order.moss")
        with self.assertRaisesRegex(ValueError, "inside the Moss workspace"):
            resolve_workspace_path("../outside.moss")

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

    def test_studio_run_uses_file_path_for_imports(self) -> None:
        with tempfile.TemporaryDirectory(dir=workspace_root()) as directory:
            root = Path(directory)
            (root / "helper.moss").write_text(
                """
fn shout(text: Text) -> Text {
  return text + "!"
}
""",
                encoding="utf-8",
            )
            result = analyze_source(
                """
import "helper.moss"

print(shout("moss"))
""",
                execute=True,
                path=str(root / "main.moss"),
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["output"], ["moss!"])

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

    def test_trailing_commas_in_multiline_constructs(self) -> None:
        source = """
fn pair(
  left: Text,
  right: Text,
) -> Text {
  return left + right
}

let values = [
  "m",
  "o",
]
let record = {
  name: pair(
    values[0],
    values[1],
  ),
  count: len(values),
}
let updated = record with {
  count: 3,
}

print(updated.name)
print(updated.count)
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["mo", "3"])

    def test_list_type_contract_is_checked(self) -> None:
        source = """
fn countText(words: List<Text>) -> Number {
  return len(words)
}

countText(["ok", 2])
"""
        with self.assertRaisesRegex(MossRuntimeError, "expected List<Text>"):
            self.run_source(source)

    def test_list_get_set_and_option_contract(self) -> None:
        source = """
fn maybeWord(words: List<Text>, index: Number) -> Option<Text> {
  return listGet(words, index, null)
}

fn replaceSecond(words: List<Text>) -> List<Text> {
  return listSet(words, 1, "parser")
}

let words = replaceSecond(["moss", "token"])
print(words[1])
print(maybeWord(words, 5))
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["parser", "null"])

    def test_list_slice_concat_insert_and_remove(self) -> None:
        source = """
let values = [1, 2, 4]
let inserted = listInsert(values, 2, 3)
let removed = listRemove(inserted, 0)
let sliced = listSlice(inserted, 1, 3)
let joined = listConcat(sliced, [9])

print(inserted)
print(removed)
print(sliced)
print(joined)
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["[1, 2, 3, 4]", "[2, 3, 4]", "[2, 3]", "[2, 3, 9]"])

    def test_list_insert_bounds_are_checked(self) -> None:
        with self.assertRaisesRegex(MossRuntimeError, "listInsert index out of range"):
            self.run_source("listInsert([1], 3, 2)")

    def test_option_type_contract_is_checked(self) -> None:
        source = """
fn acceptMaybeText(value: Option<Text>) -> Option<Text> {
  return value
}

acceptMaybeText(42)
"""
        with self.assertRaisesRegex(MossRuntimeError, "expected Option<Text>"):
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
print(textIndexOf("moss language", "lang"))
print(textIndexOf("moss language", "missing"))
print(textReplace("moss-lang-moss", "moss", "M"))
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["moss", "a|b|c", "bcd", "5", "-1", "M-lang-M"])

    def test_else_if_chains(self) -> None:
        source = """
fn classify(value: Number) -> Text {
  if value < 0 {
    return "negative"
  } else if value == 0 {
    return "zero"
  } else {
    return "positive"
  }
}

fn classifyText(value: Text) -> Text {
  if value == "a" {
    return "alpha"
  }
  else if value == "b" {
    return "beta"
  }
  else {
    return "other"
  }
}

print(classify(-1))
print(classify(0))
print(classify(3))
print(classifyText("b"))
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["negative", "zero", "positive", "beta"])

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

    def test_tokenizer_sketch_example_runs(self) -> None:
        source = Path("examples/self_host/tokenizer_sketch.moss").read_text(encoding="utf-8")
        output: list[str] = []
        results = Runtime(output.append, base_path=Path.cwd()).run_tests(parse_source(source))
        self.assertIn("first: IDENT:import", output)
        self.assertIn("peek past end: EOF", output)
        self.assertEqual(results, [{"name": "tokenizer sketch reads moss source", "status": "pass", "message": ""}])

    def test_parser_sketch_example_runs(self) -> None:
        source = Path("examples/self_host/parser_sketch.moss").read_text(encoding="utf-8")
        output: list[str] = []
        results = Runtime(output.append, base_path=Path.cwd()).run_tests(parse_source(source))
        self.assertIn("types: 2", output)
        self.assertIn("functions: 1", output)
        self.assertIn("lets: 2", output)
        self.assertEqual(results, [{"name": "parser sketch summarizes declarations", "status": "pass", "message": ""}])

    def test_checker_sketch_example_runs(self) -> None:
        source = Path("examples/self_host/checker_sketch.moss").read_text(encoding="utf-8")
        output: list[str] = []
        results = Runtime(output.append, base_path=Path.cwd()).run_tests(parse_source(source))
        self.assertIn("warnings: 0", output)
        self.assertIn("errors: 0", output)
        self.assertEqual(results, [{"name": "checker sketch accepts order example", "status": "pass", "message": ""}])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
import tempfile
import json
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path

from mosslang.checker import check_program
from mosslang.cli import main as cli_main, run_repl
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

    def test_cli_project_check_json_aggregates_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "good.moss").write_text("fn good() -> Number {\n  return 1\n}\n", encoding="utf-8")
            (root / "bad.moss").write_text("fn bad() uses Missing {\n  return 1\n}\n", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = cli_main(["project-check", "--json", str(root)])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["summary"]["files"], 2)
        self.assertEqual(payload["summary"]["errors"], 1)

    def test_manifest_project_info_emits_deterministic_import_graph(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["project-info", "--json", "examples/project_demo"])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["package"]["name"], "moss-project-demo")
        self.assertEqual(payload["package"]["entry"], "main.moss")
        self.assertEqual(
            payload["modules"],
            [
                {"path": "main.moss", "imports": ["modules/greeting.moss"]},
                {"path": "modules/greeting.moss", "imports": []},
            ],
        )

    def test_manifest_project_check_reports_missing_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "moss.toml").write_text(
                '[package]\nname = "broken"\nversion = "0.4.0"\nentry = "main.moss"\n',
                encoding="utf-8",
            )
            (root / "main.moss").write_text('import "missing.moss"\n', encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = cli_main(["project-check", "--json", str(root)])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertIn("import not found: missing.moss", payload["diagnostics"][0]["message"])

    def test_manifest_project_check_reports_import_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "moss.toml").write_text(
                '[package]\nname = "cycle"\nversion = "0.4.0"\nentry = "a.moss"\n',
                encoding="utf-8",
            )
            (root / "a.moss").write_text('import "b.moss"\n', encoding="utf-8")
            (root / "b.moss").write_text('import "a.moss"\n', encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = cli_main(["project-check", "--json", str(root)])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertIn("import cycle: a.moss -> b.moss -> a.moss", payload["diagnostics"][0]["message"])

    def test_manifest_project_run_executes_entry(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["project-run", "examples/project_demo"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue().strip(), "Hello, Moss")

    def test_manifest_project_test_runs_imported_tests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "moss.toml").write_text(
                '[package]\nname = "tested"\nversion = "0.4.0"\nentry = "main.moss"\n',
                encoding="utf-8",
            )
            (root / "main.moss").write_text('import "helper.moss"\n', encoding="utf-8")
            (root / "helper.moss").write_text('test "imported works" { assert(true, "works") }\n', encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = cli_main(["project-test", str(root)])
        self.assertEqual(code, 0)
        self.assertIn("PASS imported works", output.getvalue())
        self.assertIn("1/1 project tests passed", output.getvalue())

    def test_project_init_creates_runnable_manifest_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "new-project"
            output = StringIO()
            with redirect_stdout(output):
                init_code = cli_main(["project-init", str(root), "--name", "new-moss-project"])
                run_code = cli_main(["project-run", str(root)])
            manifest = (root / "moss.toml").read_text(encoding="utf-8")
        self.assertEqual(init_code, 0)
        self.assertEqual(run_code, 0)
        self.assertIn('name = "new-moss-project"', manifest)
        self.assertIn("Hello from Moss", output.getvalue())

    def test_manifest_project_check_detects_cross_module_duplicate_callable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "moss.toml").write_text(
                '[package]\nname = "duplicates"\nversion = "0.4.0"\nentry = "main.moss"\n',
                encoding="utf-8",
            )
            (root / "main.moss").write_text('import "helper.moss"\nfn shared() { print("main") }\n', encoding="utf-8")
            (root / "helper.moss").write_text('fn shared() { print("helper") }\n', encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = cli_main(["project-check", "--json", str(root)])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertTrue(any("duplicate callable 'shared'" in item["message"] for item in payload["diagnostics"]))

    def test_manifest_project_run_uses_declared_source_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "lib").mkdir()
            (root / "moss.toml").write_text(
                '[package]\nname = "roots"\nversion = "0.4.0"\nentry = "src/main.moss"\n\n'
                '[paths]\nsource = ["src", "lib"]\n',
                encoding="utf-8",
            )
            (root / "src" / "main.moss").write_text('import "greeting.moss"\nprint(greeting())\n', encoding="utf-8")
            (root / "lib" / "greeting.moss").write_text('fn greeting() -> Text { return "from lib" }\n', encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = cli_main(["project-run", str(root)])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue().strip(), "from lib")

    def test_project_lock_detects_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "moss.toml").write_text(
                '[package]\nname = "locked"\nversion = "0.4.0"\nentry = "main.moss"\n',
                encoding="utf-8",
            )
            source = root / "main.moss"
            source.write_text('print("first")\n', encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                lock_code = cli_main(["project-lock", str(root)])
                clean_code = cli_main(["project-check", "--locked", str(root)])
            source.write_text('print("changed")\n', encoding="utf-8")
            with redirect_stdout(output):
                drift_code = cli_main(["project-check", "--locked", str(root)])
        self.assertEqual(lock_code, 0)
        self.assertEqual(clean_code, 0)
        self.assertEqual(drift_code, 1)
        self.assertIn("module changed: main.moss", output.getvalue())

    def test_project_locked_run_requires_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "moss.toml").write_text(
                '[package]\nname = "unlocked"\nversion = "0.4.0"\nentry = "main.moss"\n',
                encoding="utf-8",
            )
            (root / "main.moss").write_text('print("hello")\n', encoding="utf-8")
            code = cli_main(["project-run", "--locked", str(root)])
        self.assertEqual(code, 1)

    def test_project_locked_check_reports_invalid_lock_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "moss.toml").write_text(
                '[package]\nname = "invalid-lock"\nversion = "0.4.0"\nentry = "main.moss"\n',
                encoding="utf-8",
            )
            (root / "main.moss").write_text('print("hello")\n', encoding="utf-8")
            (root / "moss.lock").write_text("[]\n", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = cli_main(["project-check", "--locked", str(root)])
        self.assertEqual(code, 1)
        self.assertIn("invalid lock file: expected an object with modules", output.getvalue())

    def test_multiline_repl_keeps_runtime_state(self) -> None:
        lines = iter(["fn double(value: Number) -> Number {", "return value * 2", "}", "", "print(double(4))"])
        output: list[str] = []
        code = run_repl(input_fn=lambda _prompt: next(lines), output_fn=output.append)
        self.assertEqual(code, 0)
        self.assertIn("8", output)

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

    def test_formatter_normalizes_expression_spacing_without_touching_strings(self) -> None:
        source = 'fn add(a:Number,b:Number)->Number {\n return a+b*2 # a+b stays here\n}\nlet text="a+b"\n'
        formatted = format_source(source)
        self.assertIn("fn add(a: Number, b: Number)->Number {", formatted)
        self.assertIn("return a + b * 2 # a+b stays here", formatted)
        self.assertIn('let text = "a+b"', formatted)
        self.assertEqual(format_source(formatted), formatted)

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

    def test_static_checker_allows_null_placeholder_to_narrow(self) -> None:
        program = parse_source(
            """
fn work() -> List<Number> {
  result = null
  result = [1, 2]
  return result
}
"""
        )
        diagnostics = check_program(program)
        self.assertFalse(any("assignment to result" in item.message for item in diagnostics))

    def test_static_checker_merges_matching_branch_types(self) -> None:
        program = parse_source(
            """
fn choose(flag: Bool) -> Number {
  result = null
  if flag {
    result = 1
  } else {
    result = 2
  }
  return result
}
"""
        )
        diagnostics = check_program(program)
        self.assertFalse(any("return from choose" in item.message for item in diagnostics))

    def test_static_checker_does_not_merge_disagreeing_branch_types(self) -> None:
        program = parse_source(
            """
fn choose(flag: Bool) -> Number {
  result = null
  if flag {
    result = 1
  } else {
    result = "two"
  }
  return result
}
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("return from choose" in item.message for item in diagnostics))

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

    def test_static_checker_reports_expression_level_location(self) -> None:
        program = parse_source(
            """
fn accept(value: Number) -> Number {
  return value
}
fn work() -> Number {
  return accept("wrong")
}
"""
        )
        diagnostics = check_program(program)
        mismatch = next(item for item in diagnostics if "argument value to accept" in item.message)
        self.assertEqual(mismatch.location.format(), "6:10")

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

    def test_static_checker_rejects_unknown_union_match_variant(self) -> None:
        program = parse_source(
            """
type Status = Pending | Paid
rule label(status: Status) -> Text =
  match status {
    Pending -> "pending"
    Missing -> "missing"
    Paid -> "paid"
  }
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("variant 'Missing' is not part of Status" in item.message for item in diagnostics))

    def test_static_checker_checks_declared_variant_payload_arity(self) -> None:
        program = parse_source(
            """
type Event = Ready | Failed(Text, Number)
rule label(event: Event) -> Text =
  match event {
    Ready -> "ready"
    Failed(message) -> message
  }
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("expects 2 payload pattern(s), got 1" in item.message for item in diagnostics))

    def test_static_checker_warns_after_match_catch_all(self) -> None:
        program = parse_source(
            """
type Status = Pending | Paid
rule label(status: Status) -> Text =
  match status {
    _ -> "unknown"
    Paid -> "paid"
  }
"""
        )
        diagnostics = check_program(program)
        self.assertTrue(any("unreachable match case after catch-all" in item.message for item in diagnostics))

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

    def test_json_parse_and_stringify_preserve_moss_values(self) -> None:
        source = """
let payload = jsonParse("{\\"name\\":\\"Moss\\",\\"count\\":4,\\"values\\":[1.5,true,null]}")
print(payload.name)
print(payload.count + 1)
print(payload.values[0])
print(jsonStringify({ count: payload.count, name: payload.name }))
"""
        _, output = self.run_source(source)
        self.assertEqual(output, ["Moss", "5", "1.5", '{"count":4,"name":"Moss"}'])

    def test_json_parse_reports_location(self) -> None:
        with self.assertRaisesRegex(MossRuntimeError, "jsonParse failed at line 1, column 8"):
            self.run_source('jsonParse("{\\"bad\\":}")\n')

    def test_json_stringify_rejects_non_json_values(self) -> None:
        with self.assertRaisesRegex(MossRuntimeError, "is not JSON-compatible"):
            self.run_source("jsonStringify(Ok(1))\n")

    def test_http_adapters_require_network_effect_and_exchange_json(self) -> None:
        requests: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"language":"Moss"}')

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                requests.append(self.rfile.read(length).decode("utf-8"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"accepted":true}')

            def log_message(self, _format: str, *_args: object) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            source = f'''
effect Network

fn fetch() -> Text uses Network {{
  return httpGet("{url}")
}}

fn send() -> Text uses Network {{
  return httpPostJson("{url}", {{ language: "Moss", version: 4 }})
}}

print(jsonParse(fetch()).language)
print(jsonParse(send()).accepted)
'''
            _, output = self.run_source(source)
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(output, ["Moss", "true"])
        self.assertEqual(requests, ['{"language":"Moss","version":4}'])

    def test_http_adapter_without_network_effect_is_checked(self) -> None:
        diagnostics = check_program(parse_source('fn fetch() -> Text { return httpGet("http://localhost") }\n'))
        self.assertTrue(any("does not declare uses Network" in item.message for item in diagnostics))

    def test_http_adapter_rejects_non_http_protocols(self) -> None:
        source = """
effect Network
fn fetch() -> Text uses Network {
  return httpGet("file:///private.txt")
}
fetch()
"""
        with self.assertRaisesRegex(MossRuntimeError, "URL must use http or https"):
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

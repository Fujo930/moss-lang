"""Tests for Python FFI (extern \"python\" fn)."""

from __future__ import annotations

import unittest
from pathlib import Path

from mosslang.parser import parse_source
from mosslang.checker import check_program
from mosslang.compiler import compile_program
from mosslang.vm import VM
from mosslang.nodes import PythonExternDecl
from io import StringIO


class PythonFFITests(unittest.TestCase):
    def test_parse_extern_decl(self):
        src = 'extern "python" fn sqrt(x: Number) -> Number = "math.sqrt"\n'
        program = parse_source(src)
        self.assertEqual(len(program.items), 1)
        item = program.items[0]
        self.assertIsInstance(item, PythonExternDecl)
        self.assertEqual(item.name, "sqrt")
        self.assertEqual(item.target, "math.sqrt")
        self.assertEqual(item.return_type, "Number")
        self.assertEqual(len(item.params), 1)

    def test_extern_sqrt_runs(self):
        src = 'extern "python" fn sqrt(x: Number) -> Number = "math.sqrt"\nlet x = sqrt(16)\nprint(x)'
        program = parse_source(src)
        buf = StringIO()
        vm = VM(output=buf.write, base_path=Path.cwd())
        mod = compile_program(program, source_path="test.moss")
        vm.load_module(mod)
        vm.run()
        self.assertIn("4", buf.getvalue())

    def test_extern_import_works(self):
        src = 'import "stdlib/moss/math.moss"\nlet x = sqrt(25)\nprint(x)'
        program = parse_source(src)
        buf = StringIO()
        vm = VM(output=buf.write, base_path=Path("stdlib/moss"))
        mod = compile_program(program, source_path="test.moss")
        vm.load_module(mod)
        vm.run()
        self.assertIn("5", buf.getvalue())

    def test_extern_multiple_functions(self):
        src = '''import "stdlib/moss/math.moss"
let x = cos(0)
let y = sqrt(9)
let z = pow(2, 3)
print(x)
print(y)
print(z)
'''
        program = parse_source(src)
        buf = StringIO()
        vm = VM(output=buf.write, base_path=Path("stdlib/moss"))
        mod = compile_program(program, source_path="test.moss")
        vm.load_module(mod)
        vm.run()
        output = buf.getvalue()
        self.assertIn("1", output)
        self.assertIn("3", output)
        self.assertIn("8", output)


if __name__ == "__main__":
    unittest.main()

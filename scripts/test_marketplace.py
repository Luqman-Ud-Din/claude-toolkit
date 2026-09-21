#!/usr/bin/env python3
"""Offline packaging regressions; no live audit targets or model calls."""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from marketplace import ROOT, inventory, readme


class PackagingTests(unittest.TestCase):
    def test_inventory_and_readme(self):
        plugins, errors = inventory(ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(sum(len(row[2]) for row in plugins), 79)
        self.assertEqual(readme(plugins, ROOT), (ROOT / 'README.md').read_text(encoding='utf-8'))
        self.assertEqual(readme(plugins, ROOT), readme(plugins, ROOT))

    def test_rejections(self):
        for defect in ('missing-skill', 'wrong-name', 'no-description', 'duplicate', 'missing-plugin'):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / '.claude-plugin').mkdir()
                entries = []
                for name in ('one', 'two'):
                    folder = root / 'plugins' / name
                    (folder / '.claude-plugin').mkdir(parents=True)
                    (folder / '.claude-plugin/plugin.json').write_text(json.dumps({'name': name}))
                    skill = folder / 'skills' / name
                    skill.mkdir(parents=True)
                    (skill / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Use when testing.\n---\n')
                    entries.append({'name': name, 'source': './plugins/' + name})
                path = root / 'plugins/one/skills/one/SKILL.md'
                if defect == 'missing-skill': path.unlink()
                if defect == 'wrong-name': path.write_text('---\nname: wrong\ndescription: Fine\n---\n')
                if defect == 'no-description': path.write_text('---\nname: one\n---\n')
                if defect == 'duplicate':
                    other = root / 'plugins/two/skills/two'
                    other.rename(other.with_name('one'))
                    (other.with_name('one') / 'SKILL.md').write_text('---\nname: one\ndescription: Fine\n---\n')
                if defect == 'missing-plugin': entries.append({'name': 'absent', 'source': './plugins/absent'})
                (root / '.claude-plugin/marketplace.json').write_text(json.dumps({'plugins': entries}))
                self.assertTrue(inventory(root)[1])
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/marketplace.py'), 'validate', '--root', str(root)], capture_output=True)
                self.assertNotEqual(result.returncode, 0)

    def test_python_syntax_and_cli_imports(self):
        env = dict(os.environ, AUDIT_CORE_ROOT=str(ROOT / 'plugins/audit-core'), PYTHONDONTWRITEBYTECODE='1')
        for path in ROOT.glob('plugins/*/skills/*/scripts/*.py'):
            source = path.read_text(encoding='utf-8')
            ast.parse(source)
            if '__main__' in source and 'argparse' in source:
                with self.subTest(path=path.name):
                    result = subprocess.run([sys.executable, str(path), '--help'], env=env, capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_isolated_hook_and_loader(self):
        bash = shutil.which('bash')
        self.assertIsNotNone(bash)
        with tempfile.TemporaryDirectory(prefix='toolkit-tests-') as tmp:
            base = Path(tmp)
            core = base / "core space ' $literal `tick`"
            app = base / 'separate app'
            shutil.copytree(ROOT / 'plugins/audit-core', core, ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT / 'plugins/audit-app', app, ignore=shutil.ignore_patterns('__pycache__'))
            envfile = base / 'session.env'
            envfile.touch()
            env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(core), CLAUDE_ENV_FILE=str(envfile), PYTHONDONTWRITEBYTECODE='1')
            env.pop('AUDIT_CORE_ROOT', None)
            hook = json.loads((core / 'hooks/hooks.json').read_text())['hooks']['SessionStart'][0]['hooks'][0]
            args = [arg.replace('${CLAUDE_PLUGIN_ROOT}', str(core)) for arg in hook['args']]
            subprocess.run([bash, *args], env=env, input='{}', text=True, check=True, capture_output=True)
            script = app / 'skills/audit-business-logic/scripts/flow_inventory.py'
            result = subprocess.run([bash, '-c', '. "$1"; "$2" "$3" --help', 'test', str(envfile), sys.executable, str(script)], env=env, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            missing = subprocess.run([sys.executable, str(script), '--help'], env=env, capture_output=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn(b'audit-core is unavailable', missing.stderr)
            # Core scripts still work with their siblings and no hook.
            local = subprocess.run([sys.executable, str(core / 'skills/audit-endpoint-inventory/scripts/inventory_endpoints.py'), '--help'], env=env, capture_output=True)
            self.assertEqual(local.returncode, 0, local.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Focused regression checks for formula delivery and the standard package layout."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_card import FormulaRenderer
from PIL import Image, ImageChops


def question(work: Path, formula=r'f(x)=x^2+1'):
    (work / 'text').mkdir(parents=True)
    (work / 'source').mkdir()
    Image.new('RGB', (20, 20), 'white').save(work / 'source/original.png')
    q = {
        'schema_version': '1.0', 'id': work.name, 'subject': 'mathematics', 'grade': '高一',
        'source': {'type': 'photo', 'file': 'source/original.png', 'rights': 'private-study'},
        'question': {'type': 'calculation', 'stem_md': f'求函数 ${formula}$ 的值。'},
        'figures': [], 'answer': {'final_md': '$2$', 'confidence': 'high'},
        'analysis': {'steps_md': '将 $x=1$ 代入。'},
        'diagnosis': {'student_answer_md': '', 'error_types': []},
        'meta': {'knowledge_points': ['函数值'], 'difficulty': 1},
        'review': {'status': 'draft', 'reviewer': '', 'date': '', 'uncertainties': []},
    }
    (work / 'text/question.json').write_text(json.dumps(q, ensure_ascii=False), encoding='utf-8')
    return q


def cli(script, *args):
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    return subprocess.run([sys.executable, str(HERE / script), *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8', env=env)


class DisplayQualityTests(unittest.TestCase):
    def test_formula_canvas_keeps_the_right_parenthesis(self):
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        with tempfile.TemporaryDirectory() as tmp:
            renderer = FormulaRenderer(Path(tmp))
            path = renderer.render('f(x)')
            actual = Image.open(path).convert('RGB')
            actual_bbox = ImageChops.difference(actual, Image.new('RGB', actual.size, 'white')).getbbox()
            # Independently measure the complete text on a generous canvas.
            fig = Figure(figsize=(3, 1), dpi=160)
            canvas = FigureCanvasAgg(fig)
            text = fig.text(.1, .3, '$f(x)$', fontsize=10)
            canvas.draw()
            extent = text.get_window_extent(canvas.get_renderer())
            self.assertGreaterEqual(actual_bbox[2] - actual_bbox[0], int(extent.width) - 2)

    def test_rebuild_does_not_reuse_the_old_clipped_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'formulas').mkdir()
            old_digest = hashlib.sha1(b'f(x)|False').hexdigest()[:12]
            old = root / 'formulas' / f'eq-{old_digest}.png'
            Image.new('RGBA', (1, 1), 'red').save(old)
            rendered = FormulaRenderer(root).render('f(x)')
            self.assertNotEqual(rendered, old)
            with Image.open(rendered) as image:
                self.assertGreater(image.width, 10)

    def test_default_finish_html_has_embedded_formula_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / '20261121-math-test-001'
            question(work)
            result = cli('run.py', 'finish', work, '--html')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            md = (work / 'card.md').read_text(encoding='utf-8')
            html = (work / 'card.html').read_text(encoding='utf-8')
            self.assertNotIn('$f(x)', md)
            self.assertIn('data:image/png;base64,', html)
            self.assertNotIn('<script', html)

    def test_failed_formula_cannot_be_reported_as_finished(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / '20261121-math-test-002'
            question(work, r'\unsupportedcommand{x}')
            result = cli('run.py', 'finish', work, '--formula-mode', 'both')
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('formula render failed', result.stdout + result.stderr)
            self.assertNotIn('build ok', result.stdout)

    def test_archive_convenience_attaches_a_self_contained_card(self):
        import run
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / '20261121-math-test-004'
            question(work)
            # Exercise the real build; intercept only the external archive action.
            with mock.patch('archive_to_workbench.main', return_value=0) as archive:
                with contextlib.redirect_stdout(io.StringIO()):
                    result = run.main(['finish', str(work), '--archive-manifest',
                                       str(work / 'result.archive.json')])
            self.assertEqual(result, 0)
            command = archive.call_args.args[0]
            attachments = [Path(command[i + 1]) for i, arg in enumerate(command) if arg == '--file']
            self.assertEqual(attachments, [work / 'card.html'])
            html = attachments[0].read_text(encoding='utf-8')
            self.assertIn('data:image/png;base64,', html)
            self.assertNotIn('<script', html)

    def test_index_links_to_card_outside_text_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / '20261121-math-test-003'
            question(work)
            (work / 'card.md').write_text('# card', encoding='utf-8')
            output = root / 'index.md'
            result = cli('build_index.py', root, '--out', output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            index = output.read_text(encoding='utf-8')
            self.assertIn('0 个跳过项', index)
            self.assertIn('20261121-math-test-003/card.md', index)


if __name__ == '__main__':
    unittest.main()

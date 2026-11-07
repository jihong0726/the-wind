import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('validator', Path(__file__).with_name('校验正文.py'))
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)

class ValidationTests(unittest.TestCase):
    def make(self, root, body, n=1):
        p = root/'01_新文档'/'01_正文'; p.mkdir(parents=True, exist_ok=True)
        (p/f'第{n:03d}章_测试.md').write_text(f'# 第{n:03d}章 测试\n\n'+body)
    def test_count_separates_punctuation_and_latin(self):
        self.assertEqual(v.counts('风， A 1\n'), {'han': 1, 'non_whitespace_including_punctuation': 4})
    def test_title_excluded(self):
        self.assertEqual(v.counts(v.chapter_body('# 第001章 风\n\n风。'))['han'], 1)
    def test_short_chapter_has_no_fixed_han_minimum(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root=Path(d); self.make(root, '风'*300)
            self.assertTrue(v.check(root)['mechanical_checks_passed'])
    def test_explicit_platform_limit_fails(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root=Path(d); self.make(root, '风'*300)
            self.assertFalse(v.check(root, min_nonwhite=600)['mechanical_checks_passed'])
    def test_real_identity_rejected_in_setting(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root=Path(d); self.make(root, '风'*400)
            (root/'settings.txt').write_text(v.BLOCKED[0])
            self.assertFalse(v.check(root)['mechanical_checks_passed'])
    def test_gap_fails(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root=Path(d); self.make(root, '风'*400,2)
            self.assertFalse(v.check(root)['mechanical_checks_passed'])
    def test_duplicated_long_paragraph_flagged(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root=Path(d); self.make(root, '风'*400+'\n\n'+'风'*400)
            self.assertTrue(v.check(root)['warnings'])
    def test_empty_body_rejected(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root=Path(d); self.make(root, ' \n ')
            self.assertFalse(v.check(root)['mechanical_checks_passed'])
    def test_explicit_maximum_rejected(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root=Path(d); self.make(root, '风'*400)
            self.assertFalse(v.check(root, max_nonwhite=300)['mechanical_checks_passed'])
    def test_mismatched_heading_rejected(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root=Path(d); self.make(root, '风'*400)
            p=root/'01_新文档'/'01_正文'/'第001章_测试.md'
            p.write_text(p.read_text().replace('第001章', '第002章'))
            self.assertFalse(v.check(root)['mechanical_checks_passed'])

    def test_extended_filename_parser_is_anchored_ascii_decimal(self):
        for name, number in [('第001章_测试.md', 1), ('第999章_测试.md', 999),
                             ('第1000章_测试.md', 1000), ('第10000章_测试.md', 10000),
                             ('第01000章_测试.md', 1000)]:
            self.assertEqual(v.chapter_number(name), number)
        for name in ['第01章_测试.md', '第１０００章_测试.md', '第1000x章_测试.md',
                     '备份第1000章_测试.md', '第1000章_测试.md.bak', '第1000章测试.md']:
            self.assertIsNone(v.chapter_number(name), name)

    def test_thousand_boundary_numeric_order_counts_and_cutoff(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root = Path(d)
            for n in reversed(range(1, 1002)):
                self.make(root, '风， A 1', n)
            for through, expected in [(None, 1001), (999, 999), (1000, 1000), (0, 0)]:
                result = v.check(root, through=through)
                self.assertTrue(result['mechanical_checks_passed'], result['errors'])
                self.assertEqual([c['number'] for c in result['chapters']], list(range(1, expected+1)))
                self.assertEqual(result['chapter_count'], expected)
                self.assertEqual(result['total_han'], expected)
                self.assertEqual(result['total_non_whitespace_including_punctuation'], expected*4)
                self.assertEqual(v.chapter_files(root, through), [root/c['path'] for c in result['chapters']])
            self.assertEqual(v.chapter_body('# 第1000章 测试\n\n风。'), '风。')

    def test_thousand_boundary_gaps_duplicates_and_title_mismatch(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root = Path(d)
            for n in range(1, 1002):
                self.make(root, '风。', n)
            path = root/'01_新文档'/'01_正文'/'第1000章_测试.md'
            original = path.read_text()
            path.unlink()
            self.assertTrue(any('contiguous and unique' in e['error'] for e in v.check(root)['errors']))
            path.write_text(original)
            duplicate = path.with_name('第01000章_重号.md')
            duplicate.write_text(original)
            self.assertTrue(any('contiguous and unique' in e['error'] for e in v.check(root)['errors']))
            duplicate.unlink()
            path.write_text(original.replace('第1000章', '第999章'))
            self.assertTrue(any('mismatch' in e['error'] for e in v.check(root)['errors']))
            self.assertTrue(v.check(root, through=999)['mechanical_checks_passed'])

    def test_release_selection_uses_shared_parser(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root = Path(d)
            for n in [101, 999, 1000, 1001]:
                self.make(root, '风。', n)
            for name in ['notes.md', '第10章_测试.md', '第1000x章_测试.md']:
                (root/'01_新文档'/'01_正文'/name).write_text('不是正文')
            (root/'01_新文档'/'01_正文'/'第998章_目录.md').mkdir()
            self.assertEqual([v.chapter_number(p.name) for p in v.chapter_files(root, 1000)], [101, 999, 1000])
            release = Path(__file__).resolve().parents[2]/'prepare_release.py'
            if not release.exists():
                self.skipTest('Local release helper is not part of the distributed manuscript')
            # Execute only the real entry-selection block, never release writes.
            tree = ast.parse(release.read_text())
            start = next(i for i, node in enumerate(tree.body)
                         if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'entries' for t in node.targets))
            end = next(i for i in range(start, len(tree.body)) if isinstance(tree.body[i], ast.For))
            selection = ast.Module(body=tree.body[start:end+1], type_ignores=[])
            namespace = {'p': root, 'v': v, 'through': 1000}
            exec(compile(selection, str(release), 'exec'), namespace)
            self.assertEqual([entry['path'].split('/')[-1] for entry in namespace['entries']],
                             [f'第{n:03d}章_测试.md' for n in [101, 999, 1000]])

    def test_history_is_excluded_but_current_files_remain_strict(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root = Path(d)
            self.make(root, '风。', 1)
            old = root/'99_旧文档'/'原始稿.txt'
            old.parent.mkdir(parents=True)
            old.write_text(v.BLOCKED[0])
            self.assertTrue(v.check(root)['mechanical_checks_passed'])
            active = root/'01_新文档'/'02_设定与大纲'/'测试.txt'
            active.parent.mkdir(parents=True)
            active.write_text(v.BLOCKED[0])
            self.assertFalse(v.check(root)['mechanical_checks_passed'])

    def test_nested_history_name_does_not_exempt_current_material(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as d:
            root = Path(d)
            self.make(root, '风。', 1)
            nested = root/'01_新文档'/'02_设定与大纲'/'99_旧文档'/'测试.txt'
            nested.parent.mkdir(parents=True)
            nested.write_text(v.BLOCKED[0])
            self.assertFalse(v.check(root)['mechanical_checks_passed'])

if __name__ == '__main__': unittest.main()

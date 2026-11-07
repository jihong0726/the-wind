import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('validator', Path(__file__).with_name('校验正文.py'))
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)

class ValidationTests(unittest.TestCase):
    def make(self, root, body, n=1):
        p = root/'正文'; p.mkdir(exist_ok=True)
        (p/f'第{n:03d}章_测试.md').write_text(f'# 第{n:03d}章 测试\n\n'+body)
    def test_count_separates_punctuation_and_latin(self):
        self.assertEqual(v.counts('风， A 1\n'), {'han': 1, 'non_whitespace_including_punctuation': 4})
    def test_title_excluded(self):
        self.assertEqual(v.counts(v.chapter_body('# 第001章 风\n\n风。'))['han'], 1)
    def test_short_chapter_has_no_fixed_han_minimum(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make(root, '风'*300)
            self.assertTrue(v.check(root)['mechanical_checks_passed'])
    def test_explicit_platform_limit_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make(root, '风'*300)
            self.assertFalse(v.check(root, min_nonwhite=600)['mechanical_checks_passed'])
    def test_real_identity_rejected_in_setting(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make(root, '风'*400)
            (root/'settings.txt').write_text(v.BLOCKED[0])
            self.assertFalse(v.check(root)['mechanical_checks_passed'])
    def test_gap_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make(root, '风'*400,2)
            self.assertFalse(v.check(root)['mechanical_checks_passed'])
    def test_duplicated_long_paragraph_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make(root, '风'*400+'\n\n'+'风'*400)
            self.assertTrue(v.check(root)['warnings'])
    def test_empty_body_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make(root, ' \n ')
            self.assertFalse(v.check(root)['mechanical_checks_passed'])
    def test_explicit_maximum_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make(root, '风'*400)
            self.assertFalse(v.check(root, max_nonwhite=300)['mechanical_checks_passed'])
    def test_mismatched_heading_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make(root, '风'*400)
            p=root/'正文'/'第001章_测试.md'
            p.write_text(p.read_text().replace('第001章', '第002章'))
            self.assertFalse(v.check(root)['mechanical_checks_passed'])

if __name__ == '__main__': unittest.main()

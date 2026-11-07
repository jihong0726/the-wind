#!/usr/bin/env python3
"""Local, read-only checks. The report is evidence of mechanical checks, not literary review."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

# Store identification tokens as code points so project documents do not reproduce names.
TOKEN_POINTS = [[97, 101, 115, 112, 97], [119, 105, 110, 116, 101, 114], [107, 97, 114, 105, 110, 97], [103, 105, 115, 101, 108, 108, 101], [110, 105, 110, 103, 110, 105, 110, 103], [23425, 23425], [37329, 26108, 28833], [37329, 29599, 24237], [26611, 26234, 25935], [26611, 30693, 29641], [21016, 30693, 29641], [20869, 27704, 32472, 37324], [20869, 27704, 26525, 21033], [23425, 33402, 21331], [45789, 45789], [52852, 47532, 45208], [50952, 53552], [51648, 51236], [44608, 48124, 51221], [50976, 51648, 48124], [50640, 49828, 54028]]
BLOCKED = [''.join(map(chr, token)) for token in TOKEN_POINTS]

def han(c: str) -> bool:
    n = ord(c)
    return (0x3400 <= n <= 0x4DBF or 0x4E00 <= n <= 0x9FFF or
            0xF900 <= n <= 0xFAFF or 0x20000 <= n <= 0x2EE5F or
            0x30000 <= n <= 0x323AF)

def counts(body: str) -> dict:
    return {'han': sum(han(c) for c in body),
            'non_whitespace_including_punctuation': sum(not c.isspace() for c in body)}

def chapter_number(filename: str) -> int | None:
    """Parse the entire filename; ASCII decimal numbers have at least three digits."""
    match = re.fullmatch(r'第([0-9]{3,})章_.*\.md', filename)
    return int(match[1]) if match else None

def chapter_files(root: Path, through: int | None = None) -> list[Path]:
    numbered = []
    for path in (root/'正文').glob('*.md'):
        number = chapter_number(path.name)
        if path.is_file() and number is not None and (through is None or number <= through):
            numbered.append((number, path.name, path))
    return [path for _, _, path in sorted(numbered)]

def chapter_body(text: str) -> str:
    lines = text.splitlines()
    if not lines or not re.fullmatch(r'# 第[0-9]{3,}章\s+.+', lines[0]):
        raise ValueError('The first line must be the chapter title only.')
    if any(line.startswith('#') for line in lines[1:]):
        raise ValueError('Only the chapter title may use a Markdown heading.')
    return '\n'.join(lines[1:]).strip()

def check(root: Path, min_nonwhite: int | None = None, max_nonwhite: int | None = None, through: int | None = None) -> dict:
    files = chapter_files(root, through)
    errors, warnings, chapters = [], [], []
    paragraphs = defaultdict(list)
    numbers = []
    for path in files:
        number = chapter_number(path.name); numbers.append(number)
        text = path.read_text(encoding='utf-8')
        try:
            body = chapter_body(text)
        except ValueError as e:
            errors.append({'path': str(path.relative_to(root)), 'error': str(e)})
            continue
        if int(re.match(r'# 第([0-9]{3,})章', text)[1]) != number:
            errors.append({'path': path.name, 'error': 'Filename/title chapter number mismatch'})
        metrics = counts(body)
        size = metrics['non_whitespace_including_punctuation']
        if size == 0:
            errors.append({'path': path.name, 'error': 'Empty chapter body'})
        if min_nonwhite is not None and size < min_nonwhite:
            errors.append({'path': path.name, 'error': 'Below explicitly configured publication minimum', 'size': size})
        if max_nonwhite is not None and size > max_nonwhite:
            errors.append({'path': path.name, 'error': 'Above explicitly configured publication maximum', 'size': size})
        chapters.append({'number': number, 'path': str(path.relative_to(root)), **metrics,
                         'sha256': hashlib.sha256(text.encode()).hexdigest()})
        for p in re.split(r'\n\s*\n', body):
            normalized = re.sub(r'\s+', '', p)
            if len(normalized) >= 120:
                paragraphs[normalized].append(number)
    if numbers and numbers != list(range(1, max(numbers)+1)):
        errors.append({'error': 'Published chapter numbers must be contiguous and unique', 'numbers': numbers})
    if not files:
        warnings.append({'warning': 'No chapter body files found; this is not a finished manuscript.'})
    for p, ns in paragraphs.items():
        if len(ns) > 1:
            warnings.append({'warning': 'Repeated long paragraph requires review', 'chapters': ns,
                             'paragraph_sha256': hashlib.sha256(p.encode()).hexdigest()})
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix in ('.md', '.txt', '.json', '.py'):
            if '__pycache__' in path.parts: continue
            text = path.read_text(encoding='utf-8').casefold()
            for i, token in enumerate(BLOCKED):
                if token.casefold() in text:
                    errors.append({'path': str(path.relative_to(root)), 'error': 'Disallowed real-identity token', 'token_id': i+1})
    return {'scope': 'V3 only; historical sources excluded', 'through_chapter': through, 'chapter_count': len(chapters),
            'total_han': sum(c['han'] for c in chapters),
            'total_non_whitespace_including_punctuation': sum(c['non_whitespace_including_punctuation'] for c in chapters),
            'target_non_whitespace_including_punctuation': 3200000,
            'target_range': [3040000,3360000],
            'platform_word_count_equivalence_verified': False,
            'configured_chapter_nonwhite_limits': [min_nonwhite, max_nonwhite],
            'fixed_han_minimum_enforced': False,
            'literary_quality_verified_by_this_script': False,
            'chapters': chapters, 'errors': errors, 'warnings': warnings,
            'mechanical_checks_passed': not errors}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--through', type=int, help='Only include chapters up to this approved chapter number')
    parser.add_argument('--min-nonwhite', type=int, help='Only set after checking the selected platform; no default minimum')
    parser.add_argument('--max-nonwhite', type=int, help='Only set after checking the selected platform; no default maximum')
    args = parser.parse_args()
    result = check(args.root, args.min_nonwhite, args.max_nonwhite, args.through)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)+'\n'
    if args.output: args.output.write_text(rendered, encoding='utf-8')
    print(rendered)
    return 0 if result['mechanical_checks_passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())

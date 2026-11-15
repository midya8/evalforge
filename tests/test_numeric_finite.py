"""Numeric-check range controls, not model-quality evidence."""
from decimal import Decimal, localcontext
import json
import random
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evalforge.core import EvalForgeError, Task
from evalforge.scorers import score_task


def evaluate(value, output, **options):
    task = Task.from_dict({'id': 'number', 'prompt': 'number',
                          'checks': [{'type': 'numeric', 'value': value, **options}]})
    return score_task(task, output)


class NumericFiniteTests(unittest.TestCase):
    def test_invalid_tolerances_rejected_even_without_a_number(self):
        for field in ('tolerance', 'relative_tolerance'):
            for value in (float('nan'), float('inf'), -float('inf'), -1, True,
                          None, [], {}, 'bad', 'nan', 'inf', 10**1000):
                for output in ('0', 'no number'):
                    with self.subTest(field=field, value=str(value)[:30], output=output):
                        with self.assertRaises(EvalForgeError):
                            evaluate(0, output, **{field: value})
        for value in (True, float('nan'), float('inf'), 10**1000):
            with self.assertRaises(EvalForgeError):
                evaluate(value, '0')

    def test_overflowed_output_is_a_failed_check(self):
        for output in ('1e999', '-1e999', 'value +1e999 then 0'):
            score, passed, details = evaluate(0, output, tolerance=1e308)
            self.assertEqual((score, passed), (0, False))
            self.assertIn('not finite', details[0].detail)
        self.assertEqual(evaluate(0, '0 then 1e999')[:2], (1, True))

    def test_finite_boundaries_and_overflow_against_decimal(self):
        # Decimal.from_float is a separate exact-value reference. Precision 2500
        # covers all these binary64 products and subtractions without rounding.
        cases = [(1e308, '-1e308', 1e308, 0),
                 (1e308, '-1e308', 0, 2),
                 (1e308, '-1e308', 0, 1.5),
                 (1e308, '0', 0, 1.5),
                 (-1e308, '1e308', 0, 1e308),
                 (0., '5e-324', 5e-324, 0),
                 (10., '10.5', .5, 0), (10., '10.500000000000002', .5, 0)]
        rng = random.Random(20261115)
        for _ in range(120):
            value = rng.choice((-1, 1)) * rng.uniform(.5, 1.5) * 1e308
            actual = rng.choice((-1, 1)) * rng.uniform(.5, 1.5) * 1e308
            relative = rng.uniform(0, 4)
            cases.append((value, repr(actual), 0., relative))
        self.assertEqual(len(cases), 128)
        with localcontext() as context:
            context.prec = 2500
            for value, output, absolute, relative in cases:
                a, b, t, r = map(Decimal.from_float, map(float, (value, output, absolute, relative)))
                reference = abs(a-b) <= max(t, abs(a)*r)
                with self.subTest(value=value, output=output, absolute=absolute, relative=relative):
                    self.assertEqual(evaluate(value, output, tolerance=absolute,
                                              relative_tolerance=relative)[1], reference)
        # Keep earlier first-number and convertible tolerance behavior.
        self.assertTrue(evaluate(100, '100.5', relative_tolerance='.01')[1])
        self.assertFalse(evaluate(100, '101.1 then 100', relative_tolerance=.01)[1])

    def test_cli_invalid_check_has_no_success_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tasks = root/'tasks.jsonl'
            out = root/'run.json'
            for check in ({'value': 0, 'tolerance': 'inf'}, {'value': 0, 'relative_tolerance': 'nan'}):
                tasks.write_text(json.dumps({'id': 'number', 'prompt': 'number',
                    'checks': [{'type': 'numeric', **check}]})+'\n')
                result = subprocess.run([sys.executable, '-m', 'evalforge', 'run',
                    '--tasks', str(tasks), '--cmd', f'{sys.executable} -c "print(0)"',
                    '--out', str(out)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('finite and non-negative', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()

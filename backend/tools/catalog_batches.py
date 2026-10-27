"""Run saved, capped catalog batches with at most three concurrent workers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run(name):
    result = subprocess.run([sys.executable, str(ROOT/'backend/tools/multi_retailer_collect.py'),
                             'batch', '--job', str(ROOT/'backend/data/multi-retailer'/f'{name}-job.json')],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    return name, result.returncode, result.stdout, result.stderr


if __name__ == '__main__':
    failed = False
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(run, name) for name in sys.argv[1:]]):
            name, code, output, error = future.result()
            print(output.strip() or f'{name}: no output', flush=True)
            if code:
                failed = True
                print(f'{name}: stopped: {error.strip().splitlines()[-1]}', flush=True)
    raise SystemExit(1 if failed else 0)

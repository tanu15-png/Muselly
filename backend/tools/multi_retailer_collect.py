"""Resumable, budget-capped catalog collection. Never called by the shopping API."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import sys
import time

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'backend/data/multi-retailer'
TERMINAL = {'SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'}


@contextmanager
def budget_lock():
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT/'budget.lock').open('a+b') as handle:
        handle.seek(0)
        if sys.platform == 'win32':
            import msvcrt
            deadline = time.monotonic() + 90
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline: raise
                    time.sleep(.2)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try: yield
        finally:
            handle.seek(0)
            if sys.platform == 'win32': msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / name
    temporary = target.with_suffix(target.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(target)


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def client():
    token = dotenv_values(ROOT / 'backend/.env').get('APIFY_API_TOKEN')
    if not token:
        raise RuntimeError('APIFY_API_TOKEN missing from backend/.env')
    return httpx.Client(base_url='https://api.apify.com/v2',
                        headers={'Authorization': 'Bearer ' + token},
                        verify=ssl.create_default_context(), timeout=35)


def usage(c):
    response = c.get('/users/me/usage/monthly')
    response.raise_for_status()
    data = response.json()['data']
    used = data['totalUsageCreditsUsdAfterVolumeDiscount']
    write('latest-usage.json', {'checked_at': datetime.now(timezone.utc).isoformat(),
                              'total_used_usd': used, 'ceiling_usd': 10, 'reserve_usd': .12})
    return used


def reconcile(c, name, run, row_count):
    response = c.get('/actor-runs/' + run['id'])
    response.raise_for_status()
    data = response.json()['data']
    counts = data.get('chargedEventCounts') or {}
    accounted = data.get('accountedChargedEventCounts') or {}
    prices = (data.get('pricingInfo') or {}).get('pricingPerEvent', {}).get('actorChargeEvents', {})
    primary = [key for key, event in prices.items() if event.get('isPrimaryEvent')]
    settled = counts == accounted and (not row_count or primary and sum(counts.get(k, 0) for k in primary) >= row_count)
    record = {k: data.get(k) for k in ['id', 'status', 'statusMessage', 'usageTotalUsd', 'chargedEventCounts', 'startedAt', 'finishedAt']}
    record['billing_settled'] = bool(settled)
    write(name+'-status.json', record)
    return record


def collect(c, name, actor, payload, cap, run_timeout=240, memory_mbytes=None):
    # Durable run IDs prevent duplicate charges when a command is resumed.
    path = OUT / (name + '-run.json')
    if path.exists():
        run = read(path.name)
        if run['input'] != payload or run['actor'] != actor:
            raise RuntimeError('Saved input differs; use a new batch name.')
    else:
        with budget_lock():
            reserved = 0
            for saved in OUT.glob('*-run.json'):
                status_path = saved.with_name(saved.name.replace('-run.json', '-status.json'))
                status = read(status_path.name) if status_path.exists() else {}
                if status.get('status') not in TERMINAL or not status.get('billing_settled'):
                    reserved += read(saved.name).get('max_charge_usd', 0)
            if usage(c) + reserved + cap > 9.88:
                raise RuntimeError('Budget ceiling reached; no new run started.')
            options = {'timeout': run_timeout, 'maxTotalChargeUsd': cap}
            if memory_mbytes: options['memory'] = memory_mbytes
            response = c.post('/acts/' + actor + '/runs', params=options, json=payload)
            if response.status_code not in (200, 201):
                raise RuntimeError(f'Actor start HTTP {response.status_code}; not retried.')
            data = response.json()['data']
            run = {'id': data['id'], 'dataset_id': data['defaultDatasetId'],
                   'actor': actor, 'input': payload, 'max_charge_usd': cap}
            write(path.name, run)
    deadline = time.monotonic() + 420
    while time.monotonic() < deadline:
        response = c.get('/actor-runs/' + run['id'], params={'waitForFinish': 15})
        response.raise_for_status()
        status = response.json()['data']
        write(name + '-status.json', {k: status.get(k) for k in
              ['id', 'status', 'statusMessage', 'usageTotalUsd', 'chargedEventCounts', 'startedAt', 'finishedAt']})
        if status['status'] in TERMINAL:
            break
        time.sleep(1)
    else:
        raise RuntimeError('Run still active; resume this batch, do not start a duplicate.')
    response = c.get('/datasets/' + run['dataset_id'] + '/items',
                     params={'clean': 'true', 'format': 'json', 'limit': 5000})
    response.raise_for_status()
    rows = response.json()
    write(name + '-raw.json', rows)
    # Automatic dataset billing can arrive after SUCCEEDED. Keep the full cap
    # reserved until Apify reports those events as accounted for.
    for attempt in range(4):
        status = reconcile(c, name, run, len(rows))
        if status['billing_settled']: break
        time.sleep(2)
    print(json.dumps({'batch': name, 'status': status['status'], 'rows': len(rows),
                      'charge_usd': status.get('usageTotalUsd')}, ensure_ascii=True), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['pilots', 'usage', 'batch', 'reconcile'])
    parser.add_argument('--job')
    args = parser.parse_args()
    with client() as c:
        if args.phase == 'reconcile':
            for path in OUT.glob('*-run.json'):
                name = path.name.removesuffix('-run.json')
                raw = OUT/(name+'-raw.json')
                if raw.exists():
                    status = reconcile(c,name,read(path.name),len(read(raw.name)))
                    print(json.dumps({'batch':name,'charge_usd':status['usageTotalUsd'],'settled':status['billing_settled']}),flush=True)
            print(json.dumps({'used_usd':usage(c)})); return
        if args.phase == 'usage':
            print(json.dumps({'used_usd': usage(c)})); return
        if args.phase == 'batch':
            job = json.loads(Path(args.job).read_text(encoding='utf-8'))
            collect(c, **job); return
        collect(c, 'ajio-pilot', 'thirdwatch~ajio-scraper',
                {'queries': ['women floral dress'], 'category': 'women-dresses',
                 'maxResults': 20, 'minPrice': 200, 'maxPrice': 3000}, .08)
        collect(c, 'nykaa-pilot', 'stealth_mode~nykaafashion-product-search-scraper',
                {'keyword': 'dress', 'gender': '5197_', 'price_range': '200-3000',
                 'max_items_per_url': 20, 'ignore_url_failures': False}, .13)


if __name__ == '__main__':
    main()

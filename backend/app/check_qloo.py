"""Read-only capability check: python -m app.check_qloo (no private profile inputs)."""
import json
from time import monotonic

import httpx
from fastapi import HTTPException

from .config import get_settings
from .qloo import QlooClient


def main():
    settings = get_settings()
    if not settings.qloo_api_key:
        raise SystemExit('Set QLOO_API_KEY and QLOO_BASE_URL in backend/.env before running this check.')
    inputs = [('Zara', 'brand'), ('Taylor Swift', 'artist'),
              *[(name, 'brand') for name in ('SHEIN', 'Myntra', 'AJIO', 'Amazon Fashion', 'Flipkart', 'Nykaa Fashion')]]
    with httpx.Client(follow_redirects=False) as client:
        qloo = QlooClient(client)
        try:
            deadline = monotonic() + 50
            coverage = [qloo.resolve(settings, {'input': name, 'kind': kind, 'question_id': 'capability-check'}, deadline)
                        for name, kind in inputs]
            # Only known favorite-brand/artist test inputs seed this synthetic check.
            affinities = qloo.enrich(settings, [{'input': name, 'kind': kind, 'question_id': 'capability-check'}
                                              for name, kind in inputs[:2]])
        except HTTPException as failure:
            raise SystemExit(f'Qloo check failed ({failure.status_code}): {failure.detail}') from None
    print(json.dumps({'coverage': coverage, 'sample_affinities': affinities}, indent=2))


if __name__ == '__main__':
    main()

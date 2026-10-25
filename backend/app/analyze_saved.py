"""Server-operator CLI for a requested live analysis; never an authentication bypass route."""
import argparse
import json
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette.requests import Request

from .analysis import analyze
from .auth import AuthUser
from .config import get_settings
from .database import get_engine
from .main import create_app
from .models import UserProfile


def main():
    parser = argparse.ArgumentParser(description='Analyze an explicitly selected saved account using backend credentials.')
    parser.add_argument('--user-id', required=True, type=UUID)
    parser.add_argument('--output', type=Path, help='Optional private JSON export; keep it outside version control.')
    parser.add_argument('--force', action='store_true', help='Regenerate even if matching inputs were already analyzed.')
    args = parser.parse_args()
    app = create_app(get_settings())
    with httpx.Client(timeout=60) as storage_client, httpx.Client(timeout=120) as analysis_client, Session(get_engine()) as db:
        app.state.storage_client, app.state.analysis_client = storage_client, analysis_client
        profile = db.get(UserProfile, args.user_id)
        if not profile:
            parser.error('No saved profile exists for that user ID.')
        user = AuthUser(id=profile.id, email=profile.email, display_name=profile.display_name)
        try:
            result = analyze(Request({'type': 'http', 'app': app}), force=args.force, user=user, db=db)
        except HTTPException as failure:
            print(json.dumps({'status_code': failure.status_code, 'detail': failure.detail}))
            raise SystemExit(1) from None
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('w', encoding='utf-8') as output:
                args.output.chmod(0o600)
                json.dump(jsonable_encoder(result), output, indent=2, ensure_ascii=False)
        print(json.dumps({'id': str(result['id']), 'status': result['status'], 'model': result['model'],
                          'images_analyzed': len(result['result']['images']), 'stale': result['stale'],
                          'summary': result['result']['summary'], 'usage': result['usage']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

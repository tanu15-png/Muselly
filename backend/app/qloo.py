"""Bounded, backend-only Qloo requests and conservative identity resolution."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from threading import Lock
from time import monotonic
import unicodedata
from uuid import UUID

import httpx
from fastapi import HTTPException

RESOLVER_VERSION = 'qloo-v2'
MAX_SIGNALS = 24
MAX_RESULTS = 20
MUSIC_GENRES = 'urn:tag:genre:music'
FASHION_CATEGORIES = {'urn:tag:genre:brand:fashion', 'urn:tag:genre:brand:retail:fashion'}
# These are name aliases for the music question, never invented provider IDs.
MUSIC_LABELS = {
    'k-pop': ['K Pop', 'K-pop', 'Kpop', 'Korean Pop'],
    'hip-hop / rap': ['Hip Hop', 'Hip-hop', 'Rap'],
    'electronic / edm': ['Electronic', 'Electronic Dance Music', 'EDM'],
    'r&b': ['R&B', 'Rhythm and Blues'],
}


def metrics(item):
    query = item.get('query') or {}
    if not isinstance(query, dict):
        raise invalid_response()
    values = {}
    for key in ('score', 'affinity'):
        value = item.get(key, query.get(key))
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise invalid_response()
            values[key] = value
    return values


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def matching_name(value):
    # Preserve meaningful punctuation (e.g. H&M is not automatically HM).
    # Any other spelling variation must be an alias returned by Qloo.
    return normalized(value).replace('’', "'")


def invalid_response():
    return HTTPException(502, 'Qloo returned an invalid response. Your saved style profile is unchanged.')


def entity(item):
    if not isinstance(item, dict):
        raise invalid_response()
    try:
        id = str(UUID(item['entity_id']))
        name = item['name']
        subtype = item.get('subtype') or item.get('type')
        if not isinstance(subtype, str) or not subtype.startswith('urn:entity:'):
            types = item.get('types', [])
            typed = [t for t in types if isinstance(t, str) and t.startswith('urn:entity:')] if isinstance(types, list) else []
            subtype = typed[0] if len(set(typed)) == 1 else None
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError()
        if not isinstance(subtype, str) or not subtype.startswith('urn:entity:'):
            raise ValueError()
    except (KeyError, ValueError, TypeError, AttributeError):
        raise invalid_response() from None
    return {'entity_id': id, 'name': name.strip(), 'type': subtype}


class QlooClient:
    def __init__(self, client):
        self.client = client
        self.cache = OrderedDict()
        self.lock = Lock()

    def get(self, settings, path, params, *, deadline, ttl=0, refresh=False, no_results=False, timeout_seconds=8):
        namespace = hashlib.sha256(settings.qloo_api_key.encode()).hexdigest()
        key = (settings.qloo_base_url, namespace, RESOLVER_VERSION, path, json.dumps(params, sort_keys=True))
        with self.lock:
            cached = self.cache.get(key)
            if cached and cached[0] > monotonic() and not refresh:
                self.cache.move_to_end(key)
                return deepcopy(cached[1])
        for attempt in range(2):
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise HTTPException(504, 'Qloo enrichment timed out. Please retry.')
            try:
                response = self.client.get(settings.qloo_base_url.rstrip('/') + path,
                    params=params, headers={'X-Api-Key': settings.qloo_api_key, 'Accept': 'application/json'},
                    timeout=min(timeout_seconds, remaining))
            except (httpx.TimeoutException, httpx.RequestError) as failure:
                if attempt == 0:
                    continue
                status = 504 if isinstance(failure, httpx.TimeoutException) else 503
                raise HTTPException(status, 'Qloo could not be reached in time. Please retry.') from None
            if response.status_code in (500, 502, 503, 504) and attempt == 0:
                continue
            if response.status_code == 429:
                raise HTTPException(429, 'Qloo usage limit reached. Please try again later.', headers={'Retry-After': '30'})
            if response.status_code in (401, 403):
                raise HTTPException(503, 'Qloo access is unavailable. Check the backend API key and account access.')
            if response.status_code == 404 and no_results:
                if ttl:
                    with self.lock:
                        self.cache[key] = (monotonic() + 300, [])
                        while len(self.cache) > 512:
                            self.cache.popitem(last=False)
                return []
            if response.is_error:
                raise HTTPException(503 if response.status_code >= 500 else 502,
                                    'Qloo could not complete this request. Please retry later.')
            if monotonic() > deadline:
                raise HTTPException(504, 'Qloo enrichment timed out. Please retry.')
            try:
                data = response.json()
                if not isinstance(data, dict) or data.get('success') is False:
                    raise ValueError()
                results = data['results']
                field = 'tags' if path == '/v2/tags' or params.get('filter.type') == 'urn:tag' else 'entities'
                values = results.get(field) if isinstance(results, dict) else results
                if not isinstance(values, list) or len(values) > 100:
                    raise ValueError()
                if field == 'tags':
                    values = [{**v, 'id': v.get('id') or v.get('tag_id')} if isinstance(v, dict) else v for v in values]
                # Validate before caching: a malformed provider response must not
                # poison retries for the lifetime of a successful lookup cache.
                for item in values:
                    if field == 'tags':
                        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not isinstance(item.get('id'), str):
                            raise ValueError()
                        if not item['id'].startswith('urn:tag:') or len(item['id']) > 300 or len(item['name']) > 200:
                            raise ValueError()
                    else:
                        candidate = entity(item)
                        properties = item.get('properties') or {}
                        if not isinstance(properties, dict) or not isinstance(properties.get('akas') or [], list):
                            raise ValueError()
                        if path == '/v2/insights':
                            if candidate['type'] != params.get('filter.type'):
                                raise ValueError()
                            if not isinstance(item.get('tags', []), list):
                                raise ValueError()
                            metrics(item)
            except (ValueError, KeyError, TypeError):
                raise invalid_response() from None
            if ttl:
                with self.lock:
                    self.cache[key] = (monotonic() + (ttl if values else min(ttl, 300)), deepcopy(values))
                    self.cache.move_to_end(key)
                    while len(self.cache) > 512:
                        self.cache.popitem(last=False)
            return values
        raise HTTPException(503, 'Qloo is temporarily unavailable.')

    def resolve(self, settings, signal, deadline, *, refresh=False):
        mapping = {**signal, 'status': 'unsupported', 'candidates': [],
                   'checked_at': datetime.now(timezone.utc).isoformat()}
        if len(signal['input']) > 100 or not any(c.isalnum() for c in signal['input']):
            return mapping
        if signal['kind'] == 'tag':
            music = signal['question_id'] == 'q7'
            labels = MUSIC_LABELS.get(normalized(signal['input']), [signal['input']]) if music else [signal['input']]
            params = {'filter.query': labels[0], 'take': 20}
            if music:
                params['filter.tag.types'] = MUSIC_GENRES
            values = self.get(settings, '/v2/tags', params, deadline=deadline, ttl=86400, refresh=refresh)
            matches_by_label = {matching_name(label): {} for label in labels}
            for item in values:
                if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not isinstance(item.get('id'), str):
                    raise invalid_response()
                if not item['id'].startswith('urn:tag:') or len(item['id']) > 300 or len(item['name']) > 200:
                    raise invalid_response()
                if music and not item['id'].startswith(MUSIC_GENRES + ':'):
                    continue  # Validate scope even if the provider ignores the filter.
                label = matching_name(item['name'])
                if label in matches_by_label:
                    matches_by_label[label][item['id']] = {'tag_id': item['id'], 'name': item['name']}
            # Prefer the canonical spelling. Ambiguity within that namespace
            # and spelling remains unresolved; unrelated namespaces do not count.
            matches = next((matches_by_label[matching_name(label)] for label in labels
                            if matches_by_label[matching_name(label)]), {})
        else:
            # Search has its own category syntax. Search broadly and validate returned
            # subtypes locally, so an ignored/changed types parameter cannot misresolve.
            values = self.get(settings, '/search', {'query': signal['input'], 'take': 20},
                              deadline=deadline, ttl=86400, no_results=True, refresh=refresh)
            matches = {}
            allowed = {'brand': {'urn:entity:brand'}, 'artist': {'urn:entity:artist'},
                       'inspiration': {'urn:entity:artist', 'urn:entity:person', 'urn:entity:movie', 'urn:entity:tv_show', 'urn:entity:book'}}[signal['kind']]
            for item in values:
                candidate = entity(item)
                if candidate['type'] not in allowed:
                    continue
                properties = item.get('properties') or {}
                if not isinstance(properties, dict):
                    raise invalid_response()
                names = [candidate['name']]
                for alias in properties.get('akas') or []:
                    if isinstance(alias, dict) and isinstance(alias.get('value'), str):
                        names.append(alias['value'])
                if any(matching_name(name) == matching_name(signal['input']) for name in names):
                    matches[candidate['entity_id']] = candidate
        mapping['candidates'] = list(matches.values())[:5]
        if len(matches) == 1:
            mapping.update(status='resolved', match=next(iter(matches.values())),
                           method=('music-genre-name-or-alias' if signal['question_id'] == 'q7' else 'exact-tag-name')
                           if signal['kind'] == 'tag' else 'exact-name-or-alias')
        elif len(matches) > 1:
            mapping['status'] = 'ambiguous'
        return mapping

    def enrich(self, settings, signals, *, refresh=False):
        deadline = monotonic() + 50
        resolutions = []
        for index, signal in enumerate(signals):
            if index >= MAX_SIGNALS:
                resolutions.append({**signal, 'status': 'deferred', 'candidates': []})
            else:
                resolutions.append(self.resolve(settings, signal, deadline, refresh=refresh))
        ids = sorted({r['match']['entity_id'] for r in resolutions
                      if r['status'] == 'resolved' and 'entity_id' in r['match']})
        tags = sorted({r['match']['tag_id'] for r in resolutions
                       if r['status'] == 'resolved' and 'tag_id' in r['match']})
        if not ids and not tags:
            return {'resolutions': resolutions, 'affinities': [], 'outcome': 'no-supported-signals'}
        category_tags = self.get(settings, '/v2/tags',
            {'filter.query': 'Fashion', 'filter.parents.types': 'urn:entity:brand', 'take': 20},
            deadline=deadline, ttl=86400, refresh=refresh)
        fashion_ids = sorted({item['id'] for item in category_tags if item['id'] in FASHION_CATEGORIES})
        if not fashion_ids:
            return {'resolutions': resolutions, 'affinities': [], 'outcome': 'fashion-category-unavailable'}
        params = {'filter.type': 'urn:entity:brand', 'take': MAX_RESULTS,
                  'filter.tags': ','.join(fashion_ids), 'operator.filter.tags': 'union'}
        if ids:
            params['signal.interests.entities'] = ','.join(ids)
        if tags:
            params['signal.interests.tags'] = ','.join(tags)
        values = self.get(settings, '/v2/insights', params, deadline=deadline, ttl=900, refresh=refresh)
        affinities, seen = [], set(ids)
        for rank, item in enumerate(values[:MAX_RESULTS], 1):
            candidate = entity(item)
            if candidate['type'] != 'urn:entity:brand':
                raise invalid_response()
            if candidate['entity_id'] in seen:
                continue
            seen.add(candidate['entity_id'])
            labels = item.get('tags', [])
            if not isinstance(labels, list):
                raise invalid_response()
            fashion = any(isinstance(t, dict) and any(
                str(t.get('id') or t.get('tag_id') or '').startswith(id + ':') or (t.get('id') or t.get('tag_id')) == id
                for id in fashion_ids) for t in labels)
            if not fashion:
                continue  # Do not show unrelated brands if filtering is ignored.
            candidate.update(rank=rank, category='fashion' if fashion else 'broader-brand', source='qloo',
                             evidence_entity_ids=ids, evidence_tag_ids=tags)
            candidate.update(metrics(item))
            affinities.append(candidate)
        return {'resolutions': resolutions, 'affinities': affinities, 'category_filter_tag_ids': fashion_ids,
                'outcome': 'enriched' if affinities else 'no-affinities'}

from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from app import outfits
from app import shopping_agent


def test_catalog_plan_preserves_explicit_budget_and_uses_ranked_products(monkeypatch):
    monkeypatch.setattr(shopping_agent, 'model_json', lambda *a: outfits.OutfitPlan(queries=['pink dress']))
    monkeypatch.setattr(outfits.shop, 'catalog', lambda r: [])
    observed = []
    def rank(rows, wanted, *args):
        observed.append(wanted)
        return [{'product_id': 'real-one', 'category': 'Dresses', 'price': 799, '_score': 3}]
    monkeypatch.setattr(outfits.shop, 'rank_catalog', rank)
    db = MagicMock(); db.scalars.return_value = []
    result = outfits.catalog_outfit(None, db, SimpleNamespace(id='user'), 'a dress under 1000 without red', None, [], {}, [], [])
    assert observed[0]['max_price'] == 1000
    assert 'red' in observed[0]['excluded']
    assert result[0]['product']['product_id'] == 'real-one'
    assert '_score' not in result[0]['product']


def test_no_catalog_matches_allows_inspiration(monkeypatch):
    monkeypatch.setattr(shopping_agent, 'model_json', lambda *a: outfits.OutfitPlan(queries=['dress under 100']))
    monkeypatch.setattr(outfits.shop, 'catalog', lambda r: [])
    monkeypatch.setattr(outfits.shop, 'rank_catalog', lambda *a: [])
    db = MagicMock(); db.scalars.return_value = []
    result = outfits.catalog_outfit(None, db, SimpleNamespace(id='user'), 'dress under 100', None, [], {}, [], [])
    assert result == []
    assert 'INSPIRATION MODE' in outfits.catalog_instruction(result)
    assert 'Do not claim' in outfits.catalog_instruction(result)


def test_available_products_use_catalog_instruction():
    assert 'CATALOG GROUNDING' in outfits.catalog_instruction([{'product': {}}])
    assert 'INSPIRATION MODE' not in outfits.catalog_instruction([{'product': {}}])

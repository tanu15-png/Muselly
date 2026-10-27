"""Explicit catalog source boundaries. Product identifiers are scoped by retailer."""
import re
from urllib.parse import urlparse

SOURCES = {
    'Myntra': ('', 'www.myntra.com', {'assets.myntassets.com'}),
    'AJIO': ('ajio:', 'www.ajio.com', {'assets.ajio.com'}),
    'Nykaa Fashion': ('nykaa:', 'www.nykaafashion.com', {'adn-static1.nykaa.com', 'adn-static2.nykaa.com'}),
    'SHEIN India': ('shein-india:', 'www.sheinindia.in', {'assets.ajio.com', 'assets.sheinindia.in'}),
    'H&M': ('hm:', 'www2.hm.com', {'image.hm.com', 'lp2.hm.com'}),
}


def valid_source(row):
    try:
        retailer = row.get('retailer') or 'Myntra'
        prefix, host, images = SOURCES[retailer]
        identifier = row['product_id']
        if not isinstance(identifier, str) or not identifier.startswith(prefix): return False
        source_id = identifier[len(prefix):]
        if not re.fullmatch(r'\d{1,20}(?:_[a-zA-Z0-9-]{1,35})?', source_id): return False
        if retailer not in ('AJIO','SHEIN India') and not source_id.isdigit(): return False
        url, image = urlparse(row['product_url']), urlparse(row['image_url'])
        if any(u.scheme != 'https' or u.username or u.password or u.port not in (None, 443) for u in (url, image)): return False
        if url.hostname != host or url.query or url.fragment or image.hostname not in images: return False
        if retailer == 'Myntra': return url.path.endswith('/' + source_id + '/buy')
        if retailer == 'H&M': return url.path == '/en_in/productpage.' + source_id + '.html'
        return url.path.endswith('/p/' + source_id)
    except (KeyError, TypeError, ValueError):
        return False

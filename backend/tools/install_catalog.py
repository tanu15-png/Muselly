"""Install the bundled, verified product snapshot without Apify or credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'backend/data/multi-retailer'
ARCHIVE = ROOT/'assets/catalog/muselly-catalog.zip'
FILES = ('catalog-products.json', 'validation-summary.json')


def install(archive=ARCHIVE):
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        payloads = {}
        for name in FILES:
            info = bundle.getinfo(name)
            if info.file_size > 25_000_000: raise ValueError('Snapshot exceeds supported size')
            data = bundle.read(name)
            if hashlib.sha256(data).hexdigest() != manifest['sha256'][name]:
                raise ValueError('Snapshot checksum mismatch')
            payloads[name] = data
        rows = json.loads(payloads['catalog-products.json'])
        if not isinstance(rows, list) or len(rows) != manifest['products']:
            raise ValueError('Invalid product snapshot')
        OUT.mkdir(parents=True, exist_ok=True)
        for name, data in payloads.items():
            target = OUT/name
            temporary = target.with_suffix('.install.tmp')
            temporary.write_bytes(data)
            temporary.replace(target)
    print(f'Installed {len(rows)} saved products. No scraping or API calls were made.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=ARCHIVE)
    install(parser.parse_args().archive)

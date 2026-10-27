"""Bundle only product data and validation metadata, never tokens or run/account logs."""
import hashlib
import json
from pathlib import Path
import zipfile

from install_catalog import ROOT, OUT, ARCHIVE, FILES


def package():
    report = json.loads((OUT/'validation-summary.json').read_text(encoding='utf-8'))
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'products': report['products'], 'retailers': report['retailers'],
                'checked_at': report['checked_at'], 'sha256': {}}
    temporary = ARCHIVE.with_suffix('.tmp')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for name in FILES:
            data = (OUT/name).read_bytes()
            manifest['sha256'][name] = hashlib.sha256(data).hexdigest()
            bundle.writestr(name,data)
        bundle.writestr('manifest.json',json.dumps(manifest,indent=2))
    temporary.replace(ARCHIVE)
    print(json.dumps({'products':report['products'],'retailers':report['retailers'],
                      'archive_bytes':ARCHIVE.stat().st_size,'sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()}))


if __name__ == '__main__': package()

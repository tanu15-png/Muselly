"""Bounded delivery of public catalog images whose CDN fails in some browsers."""
from collections import OrderedDict
from io import BytesIO
from threading import Lock
from time import monotonic

import httpx
from fastapi import HTTPException
from PIL import Image


class RetailerImages:
    def __init__(self, client, max_bytes=32_000_000):
        self.client, self.max_bytes = client, max_bytes
        self.cache, self.size, self.lock = OrderedDict(), 0, Lock()

    def get(self, url):
        with self.lock:
            if url in self.cache:
                self.cache.move_to_end(url)
                return self.cache[url]
        try:
            deadline = monotonic() + 25
            chunks, size = [], 0
            with self.client.stream('GET',url,timeout=httpx.Timeout(12,read=8),follow_redirects=False) as response:
                response.raise_for_status()
                if not response.headers.get('content-type','').split(';')[0].strip().startswith('image/'):
                    raise ValueError('Not an image')
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 8_000_000 or monotonic() > deadline: raise ValueError('Image limit')
                    chunks.append(chunk)
            data = b''.join(chunks)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ('JPEG','PNG','WEBP'): raise ValueError('Unsupported image')
                media_type = Image.MIME[image.format]
                image.verify()
        except (httpx.HTTPError, ValueError, OSError, Image.DecompressionBombError):
            raise HTTPException(502,'The retailer image is temporarily unavailable. Please retry.') from None
        value = (data,media_type)
        with self.lock:
            if url in self.cache: self.size -= len(self.cache.pop(url)[0])
            self.cache[url] = value; self.size += len(data)
            while self.size > self.max_bytes:
                _, removed = self.cache.popitem(last=False); self.size -= len(removed[0])
        return value

// Kept self-contained: Chrome serializes this function into an isolated world.
export function extractProducts(pageDocument = document, pageUrl = location.href) {
  const document = pageDocument, location = new URL(pageUrl);
  const host = location.hostname.replace(/^www\./, '');
  const adapters = {
    'myntra.com': { cards: '.product-base', title: '.product-product', brand: '.product-brand', price: '.product-discountedPrice, .product-price', link: 'a[href]' },
    'amazon.in': { cards: '.s-result-item[data-asin]:not([data-asin=""])', title: 'h2', brand: '[data-cy="title-recipe"] .a-row .a-size-base-plus', price: '.a-price:not(.a-text-price) .a-offscreen', link: 'a[href*="/dp/"], a[href*="/gp/product/"]' },
    'ajio.com': { cards: '.rilrtl-products-list__item', title: '.nameCls, .name', brand: '.brand', price: '.price strong, .price', link: 'a[href]' },
    'flipkart.com': { cards: '[data-id]', title: 'a[title], .KzDlHZ, .syl9yP', brand: '.syl9yP', price: '.Nx9bqj, ._30jeq3', link: 'a[href*="/p/"]' },
    'nykaafashion.com': { cards: '[data-test="product-card"], .product-item, [class*="productItem"], [class*="product-card"]', title: '[class*="product-title"], [class*="productTitle"], [class*="description"]', brand: '[class*="brand"]', price: '[class*="selling-price"], [class*="discountedPrice"], [class*="price"]', link: 'a[href*="/p/"]' },
    'sheinindia.in': { cards: '.product-list__item, .product-card, .rilrtl-products-list__item, [class*="ProductCard"]', title: '.name, .product-card__name, [class*="product-name"]', brand: '.brand', price: '.price, [class*="selling-price"]', link: 'a[href*="/p/"], a[href*="-p-"], a[href]' },
    'shein.com': { cards: '.product-list__item, .S-product-item', title: '.goods-title-link, .product-item__name', brand: '.product-item__brand', price: '.product-item__price, .normal-price-ctn__sale-price', link: 'a[href*="-p-"]' },
    'avia.com': { cards: '.product-card, .card-wrapper, .grid__item', title: '.card__heading, .product-card__title', brand: '.vendor', price: '.price-item--sale, .price-item--regular, .price', link: 'a[href*="/products/"]' },
    'prabalgurung.com': { cards: '.product-item, .product-card, .grid__item', title: '.product-item__title, .card__heading', brand: '.vendor', price: '.price, .money', link: 'a[href*="/products/"]' },
    'sachinandbabi.com': { cards: '.product-item, .product-card, .grid__item', title: '.product-item__title, .card__heading', brand: '.vendor', price: '.price, .money', link: 'a[href*="/products/"]' },
    'marchesa.com': { cards: '.product-item, .product-card, .grid__item', title: '.product-item__title, .card__heading', brand: '.vendor', price: '.price, .money', link: 'a[href*="/products/"]' },
  };
  const adapter = adapters[host];
  if (!adapter) return { items: [], supported: false, message: 'Open a supported fashion store before ranking products.' };
  const text = (node, selector) => (node.querySelector(selector)?.textContent || '').replace(/\s+/g, ' ').trim();
  const safeUrl = (value, sameHost = false) => {
    if (typeof value !== 'string' || !value.trim()) return '';
    try {
      const url = new URL(value, location.href);
      if (url.protocol !== 'https:' || url.username || url.password || (sameHost && url.hostname.replace(/^www\./, '') !== host)) return '';
      url.hash = ''; return url.href;
    } catch { return ''; }
  };
  const money = value => {
    const match = value.replace(/,/g, '').match(/(?:₹|rs\.?|inr|\$|usd|€|£)?\s*(\d+(?:\.\d{1,2})?)/i);
    return match ? match[1] : null;
  };
  const seen = new Set(), items = [];
  const productImage = image => {
    if (!image) return '';
    // A lazy image often has a data URI or placeholder in src/currentSrc.
    const candidates = [image.getAttribute('data-src'), image.getAttribute('data-original'), image.getAttribute('data-lazy-src'),
      ...(image.getAttribute('data-srcset') || image.getAttribute('srcset') || '').split(',').reverse().map(part => part.trim().split(/\s+/)[0]),
      image.currentSrc, image.getAttribute('src')];
    return candidates.map(value => safeUrl(value)).find(value => value && !/placeholder|transparent|spacer|loading\.(gif|png)/i.test(value)) || '';
  };
  for (const card of document.querySelectorAll(adapter.cards)) {
    const anchor = card.matches('a[href]') ? card : card.querySelector(adapter.link);
    const url = safeUrl(anchor?.getAttribute('href'), true);
    if (!url || seen.has(url)) continue;
    const image = card.querySelector('img');
    const title = text(card, adapter.title) || anchor?.getAttribute('title') || image?.alt || '';
    if (!title.trim()) continue;
    const rawPrice = text(card, adapter.price);
    const description = [card.innerText || card.textContent || '', image?.alt || '', anchor?.getAttribute('title') || '',
      card.getAttribute('aria-label') || ''].join(' ');
    items.push({ title: title.slice(0, 500), url, image: productImage(image),
      brand: text(card, adapter.brand).slice(0, 200), description: description.replace(/\s+/g, ' ').slice(0, 5000),
      price: money(rawPrice), currency: /€/.test(rawPrice) ? 'EUR' : /£/.test(rawPrice) ? 'GBP' : /\$|USD/.test(rawPrice) ? 'USD' : ['avia.com','prabalgurung.com','sachinandbabi.com','marchesa.com'].includes(host) ? 'USD' : 'INR',
      sold_out: /\b(sold out|out of stock)\b/i.test(description) });
    seen.add(url);
    if (items.length >= 100) break;
  }
  // Structured Product data supports product-detail pages and layout variations.
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    if (script.textContent.length > 500000 || items.length >= 100) continue;
    try {
      const visit = (node, depth = 0) => {
        if (depth > 8 || !node || items.length >= 100) return;
        if (Array.isArray(node)) { node.forEach(v => visit(v, depth + 1)); return; }
        if (typeof node !== 'object') return;
        if ([node['@type']].flat().includes('Product')) {
          const url = safeUrl(node.url || location.href, true), offer = [node.offers].flat()[0] || {};
          if (url && !seen.has(url) && typeof node.name === 'string') {
            items.push({ title: node.name.slice(0,500), url, image: safeUrl([node.image].flat()[0]?.url || [node.image].flat()[0] || ''),
              brand: String(node.brand?.name || node.brand || '').slice(0,200), description: String(node.description || '').slice(0,5000),
              price: money(String(offer.price ?? offer.lowPrice ?? '')), currency: ['INR','USD','EUR','GBP','CAD','AUD'].includes(offer.priceCurrency) ? offer.priceCurrency : 'INR',
              sold_out: /OutOfStock/.test(String(offer.availability || '')) });
            seen.add(url);
          }
        }
        for (const key of ['@graph', 'itemListElement', 'item', 'mainEntity']) visit(node[key], depth + 1);
      };
      visit(JSON.parse(script.textContent));
    } catch { /* Malformed retailer JSON must not break reading other cards. */ }
  }
  return { items, supported: true, page: location.href, title: document.title,
    message: items.length ? `Read ${items.length} loaded products. Scroll the store and rank again for more.` : 'No readable product cards found. Open a results or product page, wait for it to load, and retry. This store layout may need an adapter update.' };
}

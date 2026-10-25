import { beforeEach, expect, it } from 'vitest';
import { extractProducts } from '../../../extension/extract';

beforeEach(() => { document.body.innerHTML = ''; });

it('reads Myntra current prices and brand names while keeping missing prices unknown', () => {
  document.body.innerHTML = `<ul><li class="product-base"><a href="/dresses/one"><img src="https://assets.myntassets.com/one.jpg"><h3 class="product-brand">COS</h3><h4 class="product-product">Cream Midi Dress</h4><span class="product-discountedPrice">Rs. 1,499</span><span class="product-strike">Rs. 2,999</span></a></li><li class="product-base"><a href="/dresses/two"><h4 class="product-product">Pink Dress</h4></a></li></ul>`;
  const data = extractProducts(document, 'https://www.myntra.com/dresses');
  expect(data.items).toHaveLength(2); expect(data.items[0].price).toBe('1499');
  expect(data.items[0].brand).toBe('COS'); expect(data.items[0].url).toBe('https://www.myntra.com/dresses/one');
  expect(data.items[1].price).toBeNull(); expect(data.items[1].image).toBe('');
});

it('rejects unsupported sites, missing links and off-site cards', () => {
  document.body.innerHTML = `<li class="product-base"><h4 class="product-product">No link</h4></li><li class="product-base"><a href="https://evil.test/dress"><h4 class="product-product">Offsite</h4></a></li>`;
  expect(extractProducts(document,'https://www.myntra.com/dresses').items).toHaveLength(0);
  expect(extractProducts(document,'https://bank.example/').supported).toBe(false);
});

it('reads structured Product metadata on product-detail pages and marks sold-out offers', () => {
  document.body.innerHTML = `<script type="application/ld+json">${JSON.stringify({ '@type':'Product', name:'Floral midi dress', brand:{name:'A brand'}, image:'https://images.example/dress.jpg', offers:{price:'1999',priceCurrency:'INR',availability:'https://schema.org/OutOfStock'} })}</script>`;
  const data = extractProducts(document,'https://www.ajio.com/dress/p/123');
  expect(data.items[0].title).toBe('Floral midi dress'); expect(data.items[0].price).toBe('1999'); expect(data.items[0].sold_out).toBe(true);
});

it('uses Amazon current prices and ignores a crossed-out price', () => {
  document.body.innerHTML = `<div class="s-result-item" data-asin="B1"><a href="/dp/B1"><h2>Blue midi dress</h2><img src="https://m.media-amazon.com/dress.jpg"></a><span class="a-price a-text-price"><span class="a-offscreen">₹4,000</span></span><span class="a-price"><span class="a-offscreen">₹1,800</span></span></div>`;
  expect(extractProducts(document,'https://www.amazon.in/s?k=dress').items[0].price).toBe('1800');
});

it('prefers retailer lazy image URLs over data URIs and placeholder sources', () => {
  document.body.innerHTML = `<li class="product-base"><a href="/dress"><h4 class="product-product">Cream dress</h4><img src="data:image/gif;base64,placeholder" data-src="//assets.myntassets.com/real-dress.jpg"></a></li>`;
  expect(extractProducts(document, 'https://www.myntra.com/dresses').items[0].image).toBe('https://assets.myntassets.com/real-dress.jpg');
});

it('retains image alt metadata needed for page-card color matching', () => {
  document.body.innerHTML = `<li class="product-base"><a href="/blouse"><h4 class="product-product">Ruched Wrap Blouse</h4><img alt="Cream green floral long sleeve blouse" src="https://assets.myntassets.com/blouse.jpg"><span class="product-price">Rs. 1499</span></a></li>`;
  const product = extractProducts(document, 'https://www.myntra.com/blouses').items[0];
  expect(product.description).toContain('Cream green floral long sleeve blouse');
});

it('runs with no arguments after serialization, just as Chrome injects it', () => {
  document.body.innerHTML = `<li class="product-base"><a href="https://www.myntra.com/dress"><h4 class="product-product">Dress</h4></a></li>`;
  const injected = new Function('document','location','return (' + extractProducts.toString() + ')();');
  expect(injected(document,{href:'https://www.myntra.com/dresses'}).items).toHaveLength(1);
});

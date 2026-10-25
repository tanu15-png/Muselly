import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import ResilientImage from './ResilientImage';
afterEach(cleanup);
it('retries a failed local image once and allows an explicit retry if it still fails', () => {
  render(<ResilientImage src="/images/romantic-dress.png" alt="Saved dress" />);
  fireEvent.error(screen.getByRole('img'));
  expect(screen.getByRole('img').getAttribute('src')).toBe('/images/romantic-dress.png?preview=1');
  fireEvent.error(screen.getByRole('img'));
  fireEvent.click(screen.getByRole('button', {name:'Retry image'}));
  expect(screen.getByRole('img').getAttribute('src')).toBe('/images/romantic-dress.png?preview=2');
});
it('resets a failed preview when its source changes and omits referrers for retailer images', () => {
  const {rerender} = render(<ResilientImage src="https://store.example/one.jpg" alt="Dress" />);
  fireEvent.error(screen.getByRole('img')); fireEvent.error(screen.getByRole('img'));
  rerender(<ResilientImage src="https://store.example/two.jpg" alt="Dress" />);
  expect(screen.getByRole('img').getAttribute('src')).toBe('https://store.example/two.jpg');
  expect(screen.getByRole('img').getAttribute('referrerpolicy')).toBe('no-referrer');
});

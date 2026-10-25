import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import FashionDirectionBoard from './FashionDirectionBoard';
import { apiRequest } from '../lib/supabase';
vi.mock('../lib/supabase', () => ({ apiRequest: vi.fn() }));
vi.mock('./InspirationUploader', () => ({ PrivateImage: ({ image }) => <img alt={image.filename} src="/sample.png" /> }));
const entity = { entity_id: 'film-1', name: 'Little Women', domain: 'movie', image: '/poster.png', preference: 'like', reference_image_ids: ['look-1'], colors: ['Cream'], patterns: ['Floral'] };
const images = [{ id: 'look-1', filename: 'floral.jpg' }, { id: 'look-2', filename: 'office.jpg' }];
let changed, evidence;
beforeEach(() => { vi.resetAllMocks(); changed = vi.fn(); evidence = vi.fn(); HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); }; apiRequest.mockResolvedValue({}); });
afterEach(cleanup);
function open(entities = [entity]) { render(<FashionDirectionBoard entities={entities} images={images} ownerId="owner" onChange={changed} onEvidence={evidence} />); }
it('pairs cultural artwork with only selected looks and their attributes', () => {
  open(); expect(screen.getByAltText('Little Women cultural artwork')).toBeTruthy();
  expect(screen.getByAltText('floral.jpg')).toBeTruthy(); expect(screen.queryByAltText('office.jpg')).toBeNull();
  expect(screen.getByText('Cream')).toBeTruthy(); expect(screen.getByText('Floral')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'View floral.jpg' })); expect(evidence).toHaveBeenCalledWith(['look-1']);
});
it('edits selected looks without losing a cultural like', async () => {
  open(); fireEvent.click(screen.getByRole('button', { name: 'Edit connection' }));
  expect(screen.getByRole('button', { name: 'Select floral.jpg' }).getAttribute('aria-pressed')).toBe('true');
  fireEvent.click(screen.getByRole('button', { name: 'Select office.jpg' })); fireEvent.click(screen.getByRole('button', { name: 'Save connection' }));
  await waitFor(() => expect(changed).toHaveBeenCalledWith('film-1', true, ['look-1', 'look-2']));
  expect(apiRequest.mock.calls[0][1]).toMatchObject({ expectedOwner: 'owner', body: { preference: 'like', fashion_inspiration: true, reference_image_ids: ['look-1', 'look-2'] } });
});
it('removes the fashion connection while preserving the like and reference library', async () => {
  open(); fireEvent.click(screen.getByRole('button', { name: 'Remove connection' }));
  await waitFor(() => expect(changed).toHaveBeenCalledWith('film-1', false, undefined));
  expect(apiRequest.mock.calls[0][1].body).toEqual({ preference: 'like', fashion_inspiration: false });
});
it('keeps a connection visible when removal fails', async () => {
  apiRequest.mockRejectedValue(new Error('Connection unavailable')); open(); fireEvent.click(screen.getByRole('button', { name: 'Remove connection' }));
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Connection unavailable'); expect(changed).not.toHaveBeenCalled();
  expect(screen.getByAltText('floral.jpg')).toBeTruthy();
});
it('offers Choose looks for an unlinked save and an empty state for a new board', () => {
  open([{ ...entity, reference_image_ids: [] }]); expect(screen.getByRole('button', { name: 'Choose looks' })).toBeTruthy();
  cleanup(); open([]); expect(screen.getByText(/Save a discovery as fashion inspiration/)).toBeTruthy();
});

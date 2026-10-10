import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TasteTest from './TasteTest';
import QuestionCard from './QuestionCard';
import InspirationUploader from './InspirationUploader';
import { apiRequest, uploadInspiration } from '../lib/supabase';
import { openStylePlaceholder } from '../lib/navigation';
import { emptyAnswer, questions } from './taste';

vi.mock('../lib/supabase', () => ({ apiRequest: vi.fn(), uploadInspiration: vi.fn() }));
vi.mock('../lib/navigation', () => ({ openStylePlaceholder: vi.fn() }));

let saved;
const file = (name = 'look.png', type = 'image/png') => new File(['valid-image-in-backend-tests'], name, { type });
const metadata = id => ({ id, filename: `look-${id}.png`, updated_at: '2026-01-01', content_type: 'image/png' });
const completeAnswers = () => Object.fromEntries(questions.filter(q => !q.optional).map(q => [q.id, { ...emptyAnswer(), choices: [q.options[0].id] }]));

beforeEach(() => {
  vi.resetAllMocks();
  saved = { answers: {}, position: 0, images: [], completed_at: null };
  apiRequest.mockImplementation(async (path, options) => {
    if (options?.blob) return new Blob(['image']);
    if (options?.method === 'PUT') { saved = { ...saved, ...options.body }; return saved; }
    if (path.endsWith('/complete')) return { ...saved, completed_at: '2026-01-01' };
    return saved;
  });
  uploadInspiration.mockImplementation(async (id, value, progress) => { progress(100); return { ...metadata(id), filename: value.name }; });
  vi.stubGlobal('scrollTo', vi.fn());
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

async function open() { render(<TasteTest />); await screen.findByRole('heading', { level: 1, name: /Who are you shopping for/ }); }
async function forward() { await act(async () => { fireEvent.click(screen.getByRole('button', { name: /^Continue/ })); }); }

it('saves custom answers, restores after refresh, and preserves Back navigation', async () => {
  await open();
  expect(screen.queryByRole('button', { name: /Jump to end/ })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Other' }));
  await forward();
  expect(screen.getByRole('alert').textContent).toMatch(/Other field/);
  fireEvent.change(screen.getByLabelText(/Your answer/), { target: { value: 'Performance costumes' } });
  await forward();
  expect(saved.answers.q1.other).toBe('Performance costumes');
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/age range/);
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Back' })); });
  expect(screen.getByLabelText(/Your answer/).value).toBe('Performance costumes');
  cleanup();
  await open();
  expect(screen.getByLabelText(/Your answer/).value).toBe('Performance costumes');
});

it('autosaves Q20 location and allows skipping optional questions', async () => {
  saved.position = 4;
  render(<TasteTest />);
  const input = await screen.findByLabelText('City/region and country (optional)');
  expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Where do you currently live?');
  fireEvent.change(input, { target: { value: 'Mumbai, India' } });
  await waitFor(() => expect(saved.answers.q20.location).toBe('Mumbai, India'), { timeout: 2000 });
  await forward();
  expect(saved.answers.q20.location).toBe('Mumbai, India');
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/weekends/);
  cleanup();
  saved.position = 1;
  render(<TasteTest />);
  await screen.findByRole('heading', { name: /age range/ });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Skip' })); });
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/clothing size/);
});

it('retains unsaved choices and offers retry when persistence fails', async () => {
  await open();
  fireEvent.click(screen.getByRole('button', { name: "Women's fashion" }));
  apiRequest.mockRejectedValueOnce(new Error('Offline'));
  await forward();
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/age range/);
  expect(screen.getByText(/latest changes haven’t saved/)).toBeTruthy();
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Retry saving' })); });
  expect(saved.answers.q1.choices).toEqual(['o1']);
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/age range/);
});

it('shows a recoverable load failure without overwriting existing data', async () => {
  apiRequest.mockRejectedValueOnce(new Error('Unavailable'));
  render(<TasteTest />);
  expect((await screen.findByRole('alert')).textContent).toBe('Unavailable');
  expect(apiRequest).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await screen.findByRole('heading', { name: /Who are you/ });
});

it('enforces aesthetic selection limits and makes dislikes exclusive', () => {
  const q = questions.find(q => q.id === 'q9');
  let answer = emptyAnswer();
  const view = render(<QuestionCard question={q} answer={answer} onChange={next => { answer = next; view.rerender(<QuestionCard question={q} answer={answer} onChange={onChange} />); }} />);
  function onChange(next) { answer = next; view.rerender(<QuestionCard question={q} answer={answer} onChange={onChange} />); }
  for (const name of ['Minimal / quiet luxury', 'Streetwear', 'Soft feminine']) fireEvent.click(screen.getByRole('button', { name: new RegExp(name.replace('/', '\\/')) }));
  expect(answer.choices).toHaveLength(3);
  expect(screen.getByRole('button', { name: /Y2K/ }).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: /Streetwear/ }));
  expect(screen.getByRole('button', { name: /Y2K/ }).disabled).toBe(false);
  cleanup();
  const dislikes = questions.find(q => q.id === 'q15');
  answer = emptyAnswer();
  const dv = render(<QuestionCard question={dislikes} answer={answer} onChange={change} />);
  function change(next) { answer = next; dv.rerender(<QuestionCard question={dislikes} answer={answer} onChange={change} />); }
  fireEvent.click(screen.getByRole('button', { name: 'Neon colors' }));
  fireEvent.click(screen.getByRole('button', { name: 'No strong dislikes' }));
  expect(answer.choices).toEqual(['none']);
  fireEvent.click(screen.getByRole('button', { name: 'Loud prints' }));
  expect(answer.choices).toEqual(['o2']);
});

it('accepts multiple inspiration names as removable tags', () => {
  const q = questions.find(q => q.id === 'q8');
  let answer = emptyAnswer();
  const view = render(<QuestionCard question={q} answer={answer} onChange={change} />);
  function change(next) { answer = next; view.rerender(<QuestionCard question={q} answer={answer} onChange={change} />); }
  fireEvent.change(screen.getByLabelText('Your inspirations (optional)'), { target: { value: 'Wednesday, Zendaya,' } });
  expect(answer.text).toEqual(['Wednesday', 'Zendaya']);
  fireEvent.click(screen.getByRole('button', { name: 'Remove Wednesday' }));
  expect(answer.text).toEqual(['Zendaya']);
});

describe('inspiration uploads', () => {
  it('validates types, size, count, and permits retry after upload failure', async () => {
    const changes = vi.fn();
    render(<InspirationUploader initialImages={[]} onChange={changes} />);
    const input = screen.getByLabelText('Choose inspiration images');
    fireEvent.change(input, { target: { files: [file('x.gif', 'image/gif')] } });
    expect(screen.getByRole('alert').textContent).toMatch(/JPG/);
    const oversized = file();
    Object.defineProperty(oversized, 'size', { value: 10 * 1024 * 1024 + 1 });
    fireEvent.change(input, { target: { files: [oversized] } });
    expect(screen.getByRole('alert').textContent).toMatch(/10 MB/);
    fireEvent.change(input, { target: { files: Array.from({ length: 11 }, () => file()) } });
    expect(screen.getByRole('alert').textContent).toMatch(/up to 10/);
    expect(uploadInspiration).not.toHaveBeenCalled();
    uploadInspiration.mockRejectedValueOnce(new Error('Upload interrupted'));
    await act(async () => { fireEvent.change(input, { target: { files: [file()] } }); });
    expect(screen.getByRole('alert').textContent).toMatch(/Upload interrupted/);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Retry upload' })); });
    expect(screen.getByText('1 / 10 images uploaded')).toBeTruthy();
    expect(uploadInspiration).toHaveBeenCalledTimes(2);
    expect(uploadInspiration.mock.calls[0][0]).toBe(uploadInspiration.mock.calls[1][0]);
  });

  it('uploads five images, replaces at capacity, and persists deletion', async () => {
    const changes = vi.fn();
    render(<InspirationUploader initialImages={Array.from({ length: 5 }, (_, i) => metadata(`saved-${i}`))} onChange={changes} />);
    await act(async () => { fireEvent.change(screen.getByLabelText('Choose inspiration images'), { target: { files: Array.from({ length: 5 }, (_, i) => file(`new-${i}.png`)) } }); });
    expect(screen.getByText('10 / 10 images uploaded')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Browse images/ }).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Replace image 1' }));
    await act(async () => { fireEvent.change(screen.getByLabelText('Replace inspiration image'), { target: { files: [file('replaced.png')] } }); });
    expect(uploadInspiration.mock.lastCall[0]).toBe('saved-0');
    expect(screen.getByText('10 / 10 images uploaded')).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Remove image 1' })); });
    expect(apiRequest).toHaveBeenCalledWith('/api/onboarding/images/saved-0', { method: 'DELETE' });
    expect(screen.getByText('9 / 10 images uploaded')).toBeTruthy();
  });

  it('keeps the original image available when replacement fails', async () => {
    render(<InspirationUploader initialImages={[metadata('original')]} onChange={vi.fn()} />);
    uploadInspiration.mockRejectedValueOnce(new Error('Offline'));
    fireEvent.click(screen.getByRole('button', { name: 'Replace image 1' }));
    await act(async () => { fireEvent.change(screen.getByLabelText('Replace inspiration image'), { target: { files: [file()] } }); });
    expect(screen.getByRole('alert').textContent).toBe('Offline');
    fireEvent.click(screen.getByRole('button', { name: 'Keep previous image' }));
    expect(screen.getByText('1 / 10 images uploaded')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });
});

it('blocks fewer than five images, then saves and completes with five images', async () => {
  saved = { ...saved, answers: completeAnswers(), position: questions.length, images: Array.from({ length: 4 }, (_, i) => metadata(`id-${i}`)) };
  render(<TasteTest />);
  await screen.findByRole('heading', { level: 1, name: /Show us what/ });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Finish Taste Test/ })); });
  expect(screen.getByRole('alert').textContent).toMatch(/5–10 images/);
  expect(openStylePlaceholder).not.toHaveBeenCalled();
  await act(async () => { fireEvent.change(screen.getByLabelText('Choose inspiration images'), { target: { files: [file()] } }); });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Finish Taste Test/ })); });
  expect(apiRequest).toHaveBeenCalledWith('/api/onboarding/complete', { method: 'POST' });
  expect(openStylePlaceholder).toHaveBeenCalledOnce();
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/coming next/);
});

it('returns completed users to the saved placeholder and allows editing without resetting data', async () => {
  saved = { ...saved, completed_at: '2026-01-01', answers: completeAnswers(), images: Array.from({ length: 5 }, (_, i) => metadata(`id-${i}`)), position: questions.length };
  render(<TasteTest />);
  await screen.findByRole('heading', { name: /coming next/ });
  fireEvent.click(screen.getByRole('button', { name: /Edit my taste test/ }));
  expect(screen.getByRole('button', { name: "Women's fashion" }).getAttribute('aria-pressed')).toBe('true');
  expect(saved.completed_at).toBeTruthy();
});

it('jumps straight to inspirations while editing and saves changed choices before finishing', async () => {
  saved = { ...saved, completed_at: '2026-01-01', answers: completeAnswers(), images: Array.from({ length: 5 }, (_, i) => metadata(`id-${i}`)), position: questions.length };
  render(<TasteTest />);
  await screen.findByRole('heading', { name: /coming next/ });
  fireEvent.click(screen.getByRole('button', { name: /Edit my taste test/ }));
  fireEvent.click(screen.getByRole('button', { name: "Men's fashion" }));
  let resolveSave;
  const defaultRequest = apiRequest.getMockImplementation();
  apiRequest.mockImplementation((path, options) => {
    if (options?.method === 'PUT') return new Promise(resolve => {
      resolveSave = () => { saved = { ...saved, ...options.body }; resolve(saved); };
    });
    return defaultRequest(path, options);
  });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Jump to end/ })); });
  expect(screen.getByRole('heading', { name: /Show us what/ })).toBeTruthy();
  expect(screen.getByText('5 / 10 images uploaded')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /Jump to end/ })).toBeNull();
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Finish Taste Test/ })); });
  expect(openStylePlaceholder).not.toHaveBeenCalled();
  apiRequest.mockImplementation(defaultRequest);
  await act(async () => { resolveSave(); });
  expect(saved.answers.q1.choices).toEqual(['o2']);
  expect(saved.position).toBe(questions.length);
  expect(saved.images).toHaveLength(5);
  expect(openStylePlaceholder).toHaveBeenCalledOnce();
});


it('completes the entire twenty-question journey with persisted uploads', async () => {
  await open();
  for (const question of questions) {
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(question.title);
    if (question.optional) {
      await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Skip' })); });
    } else {
      const choice = screen.getAllByRole('button').find(button => button.hasAttribute('aria-pressed'));
      fireEvent.click(choice);
      await forward();
    }
  }
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/Show us what/);
  await act(async () => { fireEvent.change(screen.getByLabelText('Choose inspiration images'), { target: { files: Array.from({ length: 5 }, (_, i) => file(`look-${i}.png`)) } }); });
  expect(screen.getByText('5 / 10 images uploaded')).toBeTruthy();
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Finish Taste Test/ })); });
  expect(Object.keys(saved.answers)).toHaveLength(20);
  expect(openStylePlaceholder).toHaveBeenCalledOnce();
});


it('navigates immediately during slow saves and coalesces pending drafts without losing answers', async () => {
  await open();
  let resolveFirst;
  apiRequest.mockImplementationOnce((path, options) => new Promise(resolve => {
    resolveFirst = () => { saved = { ...saved, ...options.body }; resolve(saved); };
  }));
  fireEvent.click(screen.getByRole('button', { name: "Women's fashion" }));
  await forward();
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/age range/);
  expect(screen.getByRole('button', { name: /Continue/ }).disabled).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '18–24' }));
  await forward();
  fireEvent.click(screen.getByRole('button', { name: 'M', exact: true }));
  await forward();
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/daily routine/);
  // Only the first write has started while subsequent answers stay queued.
  expect(apiRequest.mock.calls.filter(([, options]) => options?.method === 'PUT')).toHaveLength(1);
  await act(async () => { resolveFirst(); });
  await waitFor(() => expect(saved.position).toBe(3));
  expect(apiRequest.mock.calls.filter(([, options]) => options?.method === 'PUT')).toHaveLength(2);
  expect(saved.answers.q1.choices).toEqual(['o1']);
  expect(saved.answers.q2.choices).toEqual(['o2']);
  expect(saved.answers.q3.choices).toEqual(['o3']);
});

it('waits for the latest queued draft before completing onboarding', async () => {
  saved = { ...saved, answers: completeAnswers(), position: questions.length, images: Array.from({ length: 5 }, (_, i) => metadata(`id-${i}`)) };
  render(<TasteTest />);
  await screen.findByRole('heading', { name: /Show us what/ });
  let resolveSave;
  apiRequest.mockImplementationOnce((path, options) => new Promise(resolve => {
    resolveSave = () => { saved = { ...saved, ...options.body }; resolve(saved); };
  }));
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Finish Taste Test/ })); });
  expect(apiRequest.mock.calls.some(([path]) => path.endsWith('/complete'))).toBe(false);
  expect(openStylePlaceholder).not.toHaveBeenCalled();
  await act(async () => { resolveSave(); });
  expect(apiRequest).toHaveBeenCalledWith('/api/onboarding/complete', { method: 'POST' });
  expect(openStylePlaceholder).toHaveBeenCalledOnce();
});

it('recovers a failed in-flight save using the latest queued answers', async () => {
  await open();
  let rejectFirst;
  apiRequest.mockImplementationOnce(() => new Promise((resolve, reject) => { rejectFirst = reject; }));
  fireEvent.click(screen.getByRole('button', { name: "Women's fashion" }));
  await forward();
  fireEvent.click(screen.getByRole('button', { name: '18–24' }));
  await forward();
  await act(async () => { rejectFirst(new Error('Temporary network failure')); });
  await waitFor(() => expect(saved.position).toBe(2));
  expect(saved.answers.q1.choices).toEqual(['o1']);
  expect(saved.answers.q2.choices).toEqual(['o2']);
  expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/clothing size/);
  expect(screen.getByText('Progress saved to your account')).toBeTruthy();
});

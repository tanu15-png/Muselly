import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import TasteAnalytics, { inspirationAnalytics } from './TasteAnalytics';
import { apiRequest } from '../lib/supabase';

vi.mock('../lib/supabase',()=>({apiRequest:vi.fn()}));
const profile={updated_at:'2026-10-20', images:[{id:'a',updated_at:'2026-10-20'}, {id:'b',updated_at:'2026-10-20'}, {id:'c',updated_at:'2026-10-21'}]};
const analysis={id:'run',completed_at:'2026-10-20',stale:true,sources:{images:profile.images.map(image=>({...image,updated_at:'2026-10-20'}))},result:{images:profile.images.map(image=>({image_id:image.id,possible_aesthetics:['Minimal','minimal'],silhouettes:['Relaxed'],patterns:[],garments:['Top'],colors:['Cream','cream','Blue']}))}};
const analytics={qloo:{status:'saved',stale:false,completed_at:'2026-10-20',brands:[{entity_id:'brand-a',name:'Discovered brand',rank:3}],input_counts:{brand:1,artist:1},inputs:[{kind:'brand',label:'Favorite brand'},{kind:'artist',label:'Favorite artist'}],unresolved_count:0},shopping:{feedback_counts:{more_like_this:2,wrong_color:1},refined_products:3,saved_products:1,last_feedback_at:'2026-10-20'}};
beforeEach(()=>{
  vi.resetAllMocks();
  URL.createObjectURL=vi.fn(()=> 'blob:analytics-test');
  URL.revokeObjectURL=vi.fn();
  apiRequest.mockImplementation((path,options)=>Promise.resolve(options?.blob ? new Blob(['image']) : analytics));
});
afterEach(cleanup);

it('counts each attribute once per unchanged inspiration and excludes replacement images',()=>{
  const data=inspirationAnalytics(analysis,profile.images);
  expect(data.observations).toHaveLength(2);
  expect(data.colors.map(row=>row.evidence_image_ids.length)).toEqual([2,2]);
});

it('links chart bars and color observations to their actual evidence',async()=>{
  const onSelect=vi.fn();render(<TasteAnalytics profile={profile} analysis={analysis} onSelect={onSelect}/>);
  fireEvent.click(screen.getByRole('button',{name:'Minimal: 2 of 2 analyzed looks. View supporting inspirations.'}));
  expect(onSelect).toHaveBeenLastCalledWith(['a','b']);
  fireEvent.click(screen.getByRole('button',{name:'Fits & shapes'}));
  expect(screen.getByRole('button',{name:'Relaxed: 2 of 2 analyzed looks. View supporting inspirations.'})).toBeTruthy();
  expect(screen.getByRole('img',{name:/Color observations: Blue 2, Cream 2/})).toBeTruthy();
  await screen.findByText('Discovered brand');
  expect(apiRequest.mock.calls.every(([,options])=>!options?.method)).toBe(true);
});

it('shows Qloo provider order and filters resolved inputs without inventing influence percentages',async()=>{
  render(<TasteAnalytics profile={profile} analysis={analysis} onSelect={vi.fn()}/>);
  await screen.findByText('Discovered brand');
  expect(screen.getByText('#3')).toBeTruthy();
  const groups=screen.getByLabelText('Resolved interests used in the saved Qloo run');
  fireEvent.click(within(groups).getByRole('button',{name:/Artists/}));
  const inputs=screen.getByLabelText('Saved Qloo input interests');
  expect(within(inputs).getByText('Favorite artist')).toBeTruthy();
  expect(within(inputs).queryByText('Favorite brand')).toBeNull();
  expect(screen.getByText(/Latest correction per product/)).toBeTruthy();
});

it('keeps inspiration charts usable after a count-loading failure and retries the read',async()=>{
  let offline=true;
  apiRequest.mockImplementation((path,options)=>{
    if(options?.blob) return Promise.resolve(new Blob(['image']));
    if(offline) {offline=false;return Promise.reject(new Error('Offline'));}
    return Promise.resolve(analytics);
  });
  render(<TasteAnalytics profile={profile} analysis={analysis} onSelect={vi.fn()}/>);
  await screen.findByRole('button',{name:'Retry analytics'});
  expect(screen.getByRole('button',{name:/Minimal: 2 of 2/})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Retry analytics'}));
  await screen.findByText('Discovered brand');
});

it('labels earlier Qloo results and avoids rendering an empty feedback chart',async()=>{
  apiRequest.mockResolvedValue({...analytics,qloo:{...analytics.qloo,stale:true},shopping:{feedback_counts:{},refined_products:0,saved_products:0}});
  render(<TasteAnalytics profile={profile} analysis={analysis} onSelect={vi.fn()}/>);
  await screen.findByText(/Earlier Qloo run/);
  expect(screen.getByRole('link',{name:/Refresh Qloo discoveries/})).toBeTruthy();
  expect(screen.getByText(/Your first correction starts the story/)).toBeTruthy();
  expect(screen.queryByText('Products (count)')).toBeNull();
});

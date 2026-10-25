import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, LockKeyhole, RefreshCw } from 'lucide-react';
import { Button, Eyebrow } from './ui';
import { apiRequest } from '../lib/supabase';
import { createDraftQueue } from '../lib/draftQueue';
import { openStylePlaceholder } from '../lib/navigation';
import { answerError, emptyAnswer, questions, stages } from './taste';
import QuestionCard from './QuestionCard';
import InspirationUploader from './InspirationUploader';
import '../styles/taste.css';

export function ProgressIndicator({ position }) {
  const stage = questions[position]?.stage ?? 4;
  const progress = Math.round(position / (questions.length + 1) * 100);
  return <div className="quiz-progress"><div className="quiz-progress-summary"><span>Stage {stage + 1} of 5 <strong>{stages[stage]}</strong></span><span>{progress}%</span></div><div role="progressbar" aria-label="Taste test progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress} className="quiz-progress-track"><span style={{ width: `${progress}%` }} /></div><ol className="quiz-stages">{stages.map((name, index) => <li key={name} aria-current={index === stage ? 'step' : undefined} className={index <= stage ? 'is-active' : ''}><span>{index < stage ? <Check size={13} aria-hidden="true" /> : index + 1}</span>{name}</li>)}</ol></div>;
}

export default function TasteTest({ header, redirectCompleted = false }) {
  const [answers, setAnswers] = useState({});
  const [position, setPosition] = useState(0);
  const [images, setImages] = useState([]);
  const [completed, setCompleted] = useState(false);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState('');
  const [saveState, setSaveState] = useState('saved');
  const [busy, setBusy] = useState(false);
  const [uploadState, setUploadState] = useState({ busy: false, unsettled: false });
  const queue = useRef(null);
  const lastQueued = useRef(null);
  const mounted = useRef(true);
  const timer = useRef(null);
  const heading = useRef(null);
  const ready = useRef(false);
  const editVersion = useRef(0);
  const question = questions[position];
  if (!queue.current) {
    queue.current = createDraftQueue(
      ({ answers, position }) => apiRequest('/api/onboarding', { method: 'PUT', body: { answers, position } }),
      (status, snapshot) => {
        if (mounted.current && snapshot.version === editVersion.current) setSaveState(status);
      },
    );
  }

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; queue.current.clear(); };
  }, []);

  useEffect(() => {
    document.title = 'Your taste test — Muselly';
    const controller = new AbortController();
    ready.current = false;
    setLoading(true); setLoadFailed(false); setError('');
    apiRequest('/api/onboarding', { signal: controller.signal }).then(data => {
      if (controller.signal.aborted) return;
      setAnswers(data.answers); setPosition(data.position); setImages(data.images);
      const params = new URLSearchParams(window.location.search);
      const edit = params.get('edit') === '1';
      setCompleted(Boolean(data.completed_at) && !edit);
      setEditing(edit);
      if (edit) {
        const questionIndex = questions.findIndex(question => question.id === params.get('question'));
        setPosition(params.get('step') === 'inspirations' ? questions.length : Math.max(0, questionIndex));
      }
      if (redirectCompleted && data.completed_at && !edit) openStylePlaceholder();
      ready.current = true;
    }).catch(failure => {
      if (!controller.signal.aborted) { setError(failure.message); setLoadFailed(true); }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { controller.abort(); clearTimeout(timer.current); };
  }, [revision, redirectCompleted]);

  const persist = useCallback((nextAnswers, nextPosition) => {
    clearTimeout(timer.current);
    lastQueued.current = { answers: nextAnswers, position: nextPosition };
    return queue.current.enqueue({ answers: nextAnswers, position: nextPosition, version: editVersion.current });
  }, []);

  useEffect(() => {
    if (!ready.current || loading || loadFailed || completed || !editVersion.current) return;
    if (lastQueued.current?.answers === answers && lastQueued.current?.position === position) return;
    timer.current = setTimeout(() => { persist(answers, position).catch(() => {}); }, 600);
    return () => clearTimeout(timer.current);
  }, [answers, position, loading, loadFailed, completed, persist]);

  useEffect(() => {
    if (!loading) heading.current?.focus({ preventScroll: true });
  }, [position, loading, completed]);

  const onUploadChange = useCallback(({ images: nextImages, busy: uploadBusy, unsettled }) => {
    setImages(nextImages); setUploadState({ busy: uploadBusy, unsettled });
  }, []);

  function changeAnswer(value) {
    editVersion.current += 1;
    setSaveState('unsaved'); setError('');
    setAnswers(previous => ({ ...previous, [question.id]: value }));
  }

  function navigate(nextPosition, skip = false) {
    if (busy || uploadState.busy) return;
    const nextAnswers = skip ? { ...answers, [question.id]: emptyAnswer() } : answers;
    if (nextPosition > position && !skip && question) {
      const problem = answerError(question, answers[question.id]);
      if (problem) { setError(problem); return; }
    }
    setError('');
    editVersion.current += 1;
    setAnswers(nextAnswers); setPosition(nextPosition);
    persist(nextAnswers, nextPosition).catch(() => {});
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  async function finish() {
    if (busy || uploadState.busy) return;
    const missing = questions.findIndex(q => answerError(q, answers[q.id]));
    if (missing >= 0) { setPosition(missing); setError('Please finish this answer before completing your taste test.'); return; }
    if (images.length < 5 || images.length > 10 || uploadState.unsettled) {
      setError('Upload 5–10 images successfully. Retry or remove any failed uploads before finishing.'); return;
    }
    setBusy(true); setError('');
    try {
      await persist(answers, questions.length);
      await apiRequest('/api/onboarding/complete', { method: 'POST' });
      setCompleted(true);
      openStylePlaceholder();
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }

  if (loading || loadFailed) return <>{header}<main id="main-content" className="quiz-page container"><p role={loadFailed ? 'alert' : 'status'}>{loading ? 'Opening your style story…' : error}</p>{loadFailed && <Button onClick={() => setRevision(value => value + 1)}><RefreshCw size={17} /> Try again</Button>}</main></>;

  if (completed) return <>{header}<main id="main-content" className="quiz-page quiz-complete container"><span className="result-icon"><Check size={26} /></span><Eyebrow>Your style story continues</Eyebrow><h1 tabIndex={-1} ref={heading}>Your taste test<br />is <em>saved.</em></h1><p>Your answers and {images.length} inspiration images are safely saved to your account. Explore your style profile or come back anytime to refine what inspires you.</p><div className="entry-actions"><Button href="/dashboard">View my Style DNA <ArrowRight size={17} /></Button><Button onClick={() => { setCompleted(false); setEditing(true); setPosition(0); setError(''); }} variant="secondary">Edit my taste test <ArrowRight size={17} /></Button></div></main></>;

  return <>{header}<main id="main-content" className="quiz-page container">
    <ProgressIndicator position={position} />
    {editing && question && <div className="quiz-edit-actions"><Button variant="secondary" disabled={busy} onClick={() => navigate(questions.length)}>Jump to end <ArrowRight size={17} /></Button></div>}
    <div className="quiz-heading"><Eyebrow>{question ? `Question ${position + 1} of ${questions.length}` : 'The final touch'}</Eyebrow><span className="question-requirement">{question?.optional ? 'Optional' : 'Required'}</span><h1 ref={heading} tabIndex={-1}>{question ? question.title : <>Show us what <em>inspires you.</em></>}</h1><p>{question ? question.hint || 'Go with your instinct. There’s no wrong answer.' : 'Upload outfits, Pinterest screenshots, saved looks, or mood boards that represent your style.'}</p></div>
    <fieldset className="quiz-fieldset" disabled={busy} aria-label={question?.title || 'Your inspirations'}>
      {question ? <QuestionCard key={question.id} question={question} answer={{ ...emptyAnswer(), ...answers[question.id] }} onChange={changeAnswer} /> : <InspirationUploader initialImages={images} onChange={onUploadChange} disabled={busy} />}
    </fieldset>
    {error && <p className="quiz-error quiz-action-error" role="alert">{error}</p>}
    <div className="quiz-actions"><Button variant="secondary" disabled={position === 0 || busy || uploadState.busy} onClick={() => navigate(position - 1)}><ArrowLeft size={17} /> Back</Button><div className="quiz-actions-right">{question?.optional && <button className="quiz-skip" type="button" disabled={busy} onClick={() => navigate(position + 1, true)}>Skip</button>}{question ? <Button onClick={() => navigate(position + 1)} disabled={busy}>{busy ? 'Saving…' : 'Continue'} <ArrowRight size={17} /></Button> : <Button onClick={finish} disabled={busy || uploadState.busy}>{busy ? 'Saving your taste…' : 'Finish Taste Test'} <ArrowRight size={17} /></Button>}</div></div>
    <div className="quiz-save-state" role="status">{saveState === 'saving' ? 'Saving your progress…' : saveState === 'saved' ? <><Check size={14} /> Progress saved to your account</> : saveState === 'error' ? <>Your latest changes haven’t saved. <button type="button" disabled={busy} onClick={() => persist(answers, position).catch(failure => setError(failure.message))}>Retry saving</button></> : 'Changes waiting to save…'}</div>
    <p className="quiz-footer"><LockKeyhole size={14} /> Personal preferences, privately saved. Take your time.</p>
  </main></>;
}

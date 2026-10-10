import { useEffect, useRef, useState } from 'react';
import { Check, ImagePlus, LockKeyhole, RefreshCw, Trash2 } from 'lucide-react';
import { apiRequest, uploadInspiration } from '../lib/supabase';
import { validateFile } from './taste';
import { Button } from './ui';

export function PrivateImage({ image, refresh = 0 }) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl;
    setUrl(''); setError(false);
    apiRequest(`/api/onboarding/images/${image.id}`, { blob: true, signal: controller.signal }).then(blob => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [image.id, image.updated_at, refresh, retry]);
  return url ? <img src={url} alt={image.filename} /> : <div className="image-loading">{error ? <><span>Preview unavailable</span><button type="button" onClick={() => setRetry(value => value + 1)}>Retry preview</button></> : <span role="status">Loading image…</span>}</div>;
}

export default function InspirationUploader({ initialImages, onChange, disabled = false }) {
  const [items, setItems] = useState(() => initialImages.map(image => ({ id: image.id, saved: image, status: 'saved' })));
  const itemsRef = useRef(items);
  const mounted = useRef(true);
  const objectUrls = useRef(new Set());
  const [errors, setErrors] = useState([]);
  const [dragging, setDragging] = useState(false);
  const input = useRef(null);
  const replaceInput = useRef(null);
  const replacing = useRef(null);
  const busy = items.some(item => ['uploading', 'deleting'].includes(item.status));
  const count = items.filter(item => item.saved).length;

  function update(transform) {
    const next = transform(itemsRef.current);
    itemsRef.current = next;
    if (mounted.current) setItems(next);
  }
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; objectUrls.current.forEach(url => URL.revokeObjectURL(url)); };
  }, []);
  useEffect(() => {
    onChange({ images: items.filter(item => item.saved).map(item => item.saved), busy, unsettled: items.some(item => item.status !== 'saved') });
  }, [items, busy, onChange]);

  async function upload(id, file) {
    update(list => list.map(item => item.id === id ? { ...item, file, status: 'uploading', error: '', progress: 0 } : item));
    try {
      const saved = await uploadInspiration(id, file, progress => update(list => list.map(item => item.id === id ? { ...item, progress } : item)));
      update(list => list.map(item => {
        if (item.id !== id) return item;
        if (item.url) { URL.revokeObjectURL(item.url); objectUrls.current.delete(item.url); }
        return { id, saved, status: 'saved' };
      }));
    } catch (failure) {
      update(list => list.map(item => item.id === id ? { ...item, status: 'failed', error: failure.message } : item));
    }
  }

  async function addFiles(fileList, replaceId = null) {
    if (disabled || busy) return;
    const files = Array.from(fileList);
    if (!files.length) return;
    const validation = [];
    if (!replaceId && files.length + itemsRef.current.length > 10) {
      setErrors(['You can upload up to 10 images. Select fewer files or remove an image first.']);
      return;
    }
    const accepted = [];
    for (const file of (replaceId ? files.slice(0, 1) : files)) {
      const error = validateFile(file);
      if (error) { validation.push(`${file.name}: ${error}`); continue; }
      const id = replaceId || crypto.randomUUID();
      const url = URL.createObjectURL(file);
      objectUrls.current.add(url);
      accepted.push({ id, file });
      update(list => replaceId ? list.map(item => {
        if (item.id !== id) return item;
        if (item.url) { URL.revokeObjectURL(item.url); objectUrls.current.delete(item.url); }
        return { ...item, url, file, status: 'uploading', progress: 0 };
      }) : [...list, { id, url, file, status: 'uploading', progress: 0 }]);
    }
    setErrors(validation);
    // Sequential uploads keep memory use modest on mobile and preserve order.
    for (const { id, file } of accepted) await upload(id, file);
  }

  async function remove(item) {
    if (busy || disabled) return;
    setErrors([]);
    if (item.saved) {
      update(list => list.map(value => value.id === item.id ? { ...value, status: 'deleting' } : value));
      try { await apiRequest(`/api/onboarding/images/${item.id}`, { method: 'DELETE' }); }
      catch (failure) {
        update(list => list.map(value => value.id === item.id ? { ...value, status: item.status } : value));
        setErrors([`Could not remove ${item.saved.filename}. ${failure.message}`]);
        return;
      }
    }
    if (item.url) { URL.revokeObjectURL(item.url); objectUrls.current.delete(item.url); }
    update(list => list.filter(value => value.id !== item.id));
  }

  return <section aria-label="Your inspiration images" className="inspiration-uploader">
    <div className={`upload-dropzone ${dragging ? 'is-dragging' : ''}`} onDragOver={event => { event.preventDefault(); if (!disabled && !busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files); }}>
      <span className="upload-symbol"><ImagePlus size={30} aria-hidden="true" /></span><h2>A little mood board. A lot of you.</h2><p>Drop your images here, or choose them from your device.</p><Button type="button" variant="secondary" disabled={disabled || busy || items.length >= 10} onClick={() => input.current.click()}>Browse images <ImagePlus size={17} /></Button>
      <small>5–10 images · JPG, JPEG, PNG, WebP · up to 10 MB each</small>
      <input ref={input} className="sr-only" tabIndex={-1} type="file" multiple accept="image/jpeg,image/png,image/webp" aria-label="Choose inspiration images" disabled={disabled || busy} onChange={event => { addFiles(event.target.files); event.target.value = ''; }} />
      <input ref={replaceInput} className="sr-only" tabIndex={-1} type="file" accept="image/jpeg,image/png,image/webp" aria-label="Replace inspiration image" disabled={disabled || busy} onChange={event => { addFiles(event.target.files, replacing.current); event.target.value = ''; }} />
    </div>
    <div className="upload-summary"><strong role="status">{count} / 10 images uploaded</strong><span>{count < 5 ? `${5 - count} more to finish your taste test` : 'Your inspirations are ready'}</span></div>
    {errors.length > 0 && <div className="quiz-error" role="alert">{errors.map((error, index) => <p key={index}>{error}</p>)}</div>}
    {items.length > 0 ? <div className="inspiration-grid">{items.map((item, index) => <article className="inspiration-tile" key={item.id} aria-label={`Inspiration ${index + 1}`}>
      <div className="inspiration-photo">{item.url ? <img src={item.url} alt={item.file.name} /> : <PrivateImage image={item.saved} />}{item.status === 'saved' && <span className="upload-check" aria-label="Uploaded"><Check size={16} /></span>}</div>
      <div className="inspiration-info"><span title={item.file?.name || item.saved?.filename}>{item.file?.name || item.saved?.filename}</span>
        {item.status === 'uploading' && <div role="status"><progress max="100" value={item.progress} aria-label={`Uploading ${item.file.name}`} /><small>{item.progress === 100 ? 'Saving securely…' : `${item.progress}% uploaded`}</small></div>}
        {item.status === 'deleting' && <small role="status">Removing…</small>}
        {item.status === 'failed' && <><p className="quiz-error" role="alert">{item.error}</p><button className="upload-retry" type="button" disabled={busy || disabled} onClick={() => upload(item.id, item.file)}><RefreshCw size={14} /> Retry upload</button>{item.saved && <button className="upload-retry" type="button" disabled={busy || disabled} onClick={() => { if (item.url) URL.revokeObjectURL(item.url); update(list => list.map(value => value.id === item.id ? { id: item.id, saved: item.saved, status: 'saved' } : value)); }}>Keep previous image</button>}</>}
        <div className="image-actions"><button type="button" disabled={busy || disabled} onClick={() => { replacing.current = item.id; replaceInput.current.click(); }} aria-label={`Replace image ${index + 1}`}><RefreshCw size={15} /> Replace</button><button type="button" disabled={busy || disabled} onClick={() => remove(item)} aria-label={`Remove image ${index + 1}`}><Trash2 size={15} /></button></div>
      </div>
    </article>)}</div> : <p className="upload-empty">A saved outfit, a screenshot, a favorite look. Start with anything you love.</p>}
    <p className="upload-privacy"><LockKeyhole size={15} aria-hidden="true" /> Your images are private to your account. Upload images you have permission to use; you can remove them anytime.</p>
  </section>;
}

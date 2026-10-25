import { useState } from 'react';
import { Check, Plus, X } from 'lucide-react';
import { emptyAnswer, toggleChoice } from './taste';

const palettes = [
  ['#eee4d5', '#c3b4a1', '#726b65'], ['#99704b', '#788063', '#b76e51'], ['#d8cce8', '#f0c8d2', '#bbd7d5'],
  ['#27232e', '#473747', '#24364c'], ['#d74852', '#e9b43b', '#406cab'], ['#fff', '#999', '#222'],
];

export function ImageOptionCard({ option, selected, disabled, onClick }) {
  const [failed, setFailed] = useState(false);
  const outfit = option.visual === 'outfit';
  return <button type="button" className={`quiz-option quiz-option--image ${selected ? 'is-selected' : ''}`} aria-pressed={selected} disabled={disabled} onClick={onClick}>
    {failed ? <span className="option-fallback">{option.label}</span> : outfit ? <span role="img" aria-label={`${option.label} outfit example`} className="outfit-image"><img src="/images/taste/outfits.png" alt="" loading="lazy" onError={() => setFailed(true)} style={{ left: `${option.tile % 4 * -100}%`, top: `${Math.floor(option.tile / 4) * -100}%` }} /></span> : <img src={`/images/taste/${option.visual}-${option.tile}.svg`} alt={`${option.label} illustration`} loading="lazy" onError={() => setFailed(true)} />}
    <span className="option-check" aria-hidden="true">{selected ? <Check size={16} /> : <Plus size={16} />}</span><span className="option-label">{option.label}</span>
  </button>;
}

export function MultiSelectChips({ question, answer, onChange }) {
  return <div className={`quiz-options ${question.options.some(o => o.visual && o.visual !== 'palette') ? 'quiz-options--visual' : ''}`}>
    {question.options.filter(option => !option.retired || answer.choices.includes(option.id)).map(option => {
      const selected = answer.choices.includes(option.id);
      const disabled = !selected && question.multi && question.max && answer.choices.length >= question.max;
      const onClick = () => onChange(toggleChoice(question, answer, option.id));
      if (option.visual && option.visual !== 'palette') return <ImageOptionCard key={option.id} {...{ option, selected, disabled, onClick }} />;
      return <button key={option.id} type="button" className={`quiz-option ${selected ? 'is-selected' : ''} ${option.visual === 'palette' ? 'quiz-option--palette' : ''}`} aria-pressed={selected} disabled={Boolean(disabled)} onClick={onClick}>
        {option.visual === 'palette' && <span className="color-palette" aria-hidden="true">{palettes[option.tile].map(color => <i key={color} style={{ backgroundColor: color }} />)}</span>}
        <span>{option.label}</span>{selected && <Check size={16} aria-hidden="true" />}
      </button>;
    })}
  </div>;
}

export function OtherInput({ question, answer, onChange }) {
  if (!answer.choices.includes('other')) return null;
  return <div className="quiz-field"><label htmlFor={`${question.id}-other`}>Your answer <span>(required for Other)</span></label><input id={`${question.id}-other`} value={answer.other} maxLength={300} onChange={event => onChange({ ...answer, other: event.target.value })} placeholder="Tell us what feels like you…" /></div>;
}

export function TagsInput({ id, label, values, onChange, placeholder }) {
  const [draft, setDraft] = useState('');
  function add(value) {
    const names = value.split(',').map(name => name.trim()).filter(Boolean);
    onChange([...new Set([...values, ...names])].slice(0, 30));
    setDraft('');
  }
  return <div className="quiz-field"><label htmlFor={id}>{label}</label><div className="name-tags">{values.map(name => <span key={name}>{name}<button type="button" aria-label={`Remove ${name}`} onClick={() => onChange(values.filter(value => value !== name))}><X size={14} /></button></span>)}</div><input id={id} value={draft} maxLength={100} placeholder={placeholder} onChange={event => { if (event.target.value.includes(',')) add(event.target.value); else setDraft(event.target.value); }} onBlur={() => { if (draft.trim()) add(draft); }} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); add(draft); } }} /><small>Separate names with commas or press Enter. Up to 30 names.</small></div>;
}

export default function QuestionCard({ question, answer = emptyAnswer(), onChange }) {
  return <div className="question-card">
    {question.field === 'location' && <div className="quiz-field"><label htmlFor="current-location">City/region and country (optional)</label><input id="current-location" autoComplete="off" value={answer.location || ''} maxLength={200} placeholder="e.g. Mumbai, India" onChange={event => onChange({ ...answer, location: event.target.value })} /></div>}
    {question.options.length > 0 && <><div className="question-meta">{question.multi ? `Choose ${question.max ? `up to ${question.max}` : 'all that feel right'}` : 'Choose one'}{question.multi && <span role="status">{answer.choices.length} selected</span>}</div><MultiSelectChips {...{ question, answer, onChange }} /><OtherInput {...{ question, answer, onChange }} /></>}
    {question.extra && <TagsInput key={question.id} id={`${question.id}-tags`} label={question.id === 'q7' ? `${question.extra} (optional)` : 'Your inspirations (optional)'} values={answer.text} onChange={text => onChange({ ...answer, text })} placeholder={question.id === 'q8' ? question.extra : 'Singers, bands, artists…'} />}
  </div>;
}

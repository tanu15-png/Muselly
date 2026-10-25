import { useState } from 'react';

function ImagePreview({ src, alt, className, ...props }) {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const local = src?.startsWith('/images/');
  const url = local && attempt ? `${src}${src.includes('?') ? '&' : '?'}preview=${attempt}` : src;
  if (failed || !src) return <span className={`image-fallback ${className || ''}`} role="img" aria-label={alt || 'Image unavailable'}><span>{alt || 'Image unavailable'}</span>{src && <button type="button" onClick={() => { setFailed(false); setAttempt(value => value + 1); }}>Retry image</button>}</span>;
  return <img {...props} key={attempt} src={url} alt={alt} className={className} referrerPolicy="no-referrer" onError={() => {
    if (attempt === 0) setAttempt(1);
    else setFailed(true);
  }} />;
}

export default function ResilientImage(props) {
  return <ImagePreview key={props.src} {...props} />;
}

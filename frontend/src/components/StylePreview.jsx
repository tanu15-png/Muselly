import { Sparkles } from 'lucide-react';
import { Card } from './ui';

export default function StylePreview({ className = '' }) {
  return <Card className={`style-preview ${className}`}>
    <div className="style-preview__top"><span className="icon-tile"><Sparkles size={17} /></span><span className="preview-label">Illustrative preview</span></div>
    <h3>Your Style DNA</h3>
    <p>A little moodboard. A lot of you.</p>
    <div className="moodboard" aria-label="Example style inspirations">
      <img src="/images/romantic-dress.png" alt="Soft cream sleeves and a flowing brown dress" />
      <img src="/images/modern-classic.png" alt="Burgundy leather and tailored trousers" />
      <img src="/images/occasion-wear.png" alt="Delicate neutral embroidered occasion wear" />
      <img src="/images/soft-casual.png" alt="Relaxed denim and soft blue layers" />
    </div>
    <div className="style-traits">{[['Romantic', 'long'], ['Earthy tones', 'medium'], ['Timeless', 'short']].map(([name, size]) => <div className="style-trait" key={name}><span>{name}</span><span className={`trait-bar trait-bar--${size}`} aria-hidden="true"><i /></span></div>)}</div>
    <div className="palette" aria-label="Example palette: cream, sand, brown, burgundy, blue"><span /><span /><span /><span /><span /><small>A palette that feels like home</small></div>
  </Card>;
}

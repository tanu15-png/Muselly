import { ArrowUpRight, Sparkles } from 'lucide-react';

export function Button({ href, variant = 'primary', children, className = '', ...props }) {
  const Component = href ? 'a' : 'button';
  return <Component href={href} className={`button button--${variant} ${className}`} {...props}>{children}</Component>;
}

export function Brand({ onClick }) {
  return <a className="brand" href="/" aria-label="Muselly home" onClick={onClick}>muselly<span aria-hidden="true">✧</span></a>;
}

export function Eyebrow({ children, icon = false }) {
  return <span className="eyebrow">{icon && <Sparkles size={14} aria-hidden="true" />}{children}</span>;
}

export function SectionHeading({ eyebrow, title, children, centered = false }) {
  return <div className={`section-heading ${centered ? 'section-heading--center' : ''}`}><Eyebrow>{eyebrow}</Eyebrow><h2>{title}</h2>{children && <p>{children}</p>}</div>;
}

export function Card({ as: Component = 'div', className = '', children, ...props }) {
  return <Component className={`card ${className}`} {...props}>{children}</Component>;
}

export function TextLink({ href, children }) {
  return <a className="text-link" href={href}>{children}<ArrowUpRight size={17} aria-hidden="true" /></a>;
}

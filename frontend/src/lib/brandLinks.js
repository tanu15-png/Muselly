import verifiedLinks from '../../../shared/brand-links.json';

// Checked against brand sites on 2026-10-18. The two profile links come from
// Qloo's public Instagram metadata. Bind links to entity identity and name,
// never guess domains from a brand label or apply name-only matches.
export function brandLink(brand) {
  const entry = verifiedLinks[brand.entity_id?.toLowerCase()];
  if (entry && entry.name.toLocaleLowerCase() === brand.name?.trim().toLocaleLowerCase()) {
    return { href: entry.url, label: entry.kind === 'profile' ? 'Visit brand profile' : 'Visit website' };
  }
  return {
    href: `https://www.google.com/search?q=${encodeURIComponent(`${brand.name} official website`)}`,
    label: 'Find website',
  };
}

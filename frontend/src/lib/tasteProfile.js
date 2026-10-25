import { questions } from '../components/taste';

export function answerValues(answers, id) {
  const question = questions.find(item => item.id === id);
  const answer = answers[id];
  if (!question || !answer) return [];
  const choices = (answer.choices || []).map(choice => choice === 'other'
    ? answer.other || 'Other' : question.options.find(option => option.id === choice)?.label).filter(Boolean);
  return [...choices, ...(answer.text || []), ...(answer.location ? [answer.location] : [])];
}

// Merge spelling/case duplicates, without inventing a semantic style taxonomy.
export function observedAttributes(images, field) {
  const attributes = new Map();
  for (const image of images) {
    for (const raw of image[field] || []) {
      const label = raw.trim();
      const key = label.toLocaleLowerCase();
      if (!label) continue;
      if (!attributes.has(key)) attributes.set(key, { label, ids: new Set() });
      attributes.get(key).ids.add(image.image_id);
    }
  }
  return [...attributes.values()].map(({ label, ids }) => ({ attribute: label, evidence_image_ids: [...ids] }))
    .sort((a, b) => b.evidence_image_ids.length - a.evidence_image_ids.length || a.attribute.localeCompare(b.attribute));
}

export function matchingObservations(analysis, images) {
  const sources = new Map((analysis?.sources?.images || []).map(image => [image.id, image]));
  const observations = new Map((analysis?.result?.images || []).map(image => [image.image_id, image]));
  return new Map(images.filter(image => {
    const source = sources.get(image.id);
    return source && Date.parse(source.updated_at) === Date.parse(image.updated_at);
  }).map(image => [image.id, observations.get(image.id)]));
}

export function analysisExpired(analysis) {
  return analysis?.status === 'running' && Date.now() - Date.parse(analysis.created_at) > 15 * 60 * 1000;
}

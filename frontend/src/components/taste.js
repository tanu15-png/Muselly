import questions from '../../../shared/taste-questions.json';
export { questions };
export const stages = ['About You', 'Your Lifestyle', 'Your Fashion Taste', 'Shopping Habits', 'Your Inspirations'];
export const emptyAnswer = () => ({ choices: [], other: '', text: [], location: '' });

export function toggleChoice(question, answer, id) {
  let choices;
  if (!question.multi) choices = [id];
  else if (answer.choices.includes(id)) choices = answer.choices.filter(value => value !== id);
  else if (question.id === 'q15' && id === 'none') choices = ['none'];
  else {
    choices = [...answer.choices.filter(value => question.id !== 'q15' || value !== 'none'), id];
    if (question.max && choices.length > question.max) return answer;
  }
  return { ...answer, choices, other: choices.includes('other') ? answer.other : '' };
}

export function answerError(question, answer = emptyAnswer()) {
  if (!question.optional && !answer.choices.length) return 'Choose at least one option to continue.';
  if (answer.choices.includes('other') && !answer.other.trim()) return 'Tell us a little more in the Other field.';
  return '';
}

export function validateFile(file) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || !/\.(jpe?g|png|webp)$/i.test(file.name)) return 'Choose JPG, JPEG, PNG, or WebP images.';
  if (file.size > 10 * 1024 * 1024) return 'Each image must be 10 MB or smaller.';
  if (!file.size) return 'This image is empty. Choose another file.';
  return '';
}

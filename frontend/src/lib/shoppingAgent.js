export async function readAgentEvents(response, onProgress) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', result;
  function consume(line) {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === 'progress') onProgress(event.message);
    if (event.type === 'error') throw new Error(event.message);
    if (event.type === 'result') result = event.result;
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split('\n'); buffer = lines.pop();
      lines.forEach(consume);
      if (done) break;
    }
    consume(buffer);
    if (!result) throw new Error('The shopping agent was interrupted. Please retry.');
    return result;
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}

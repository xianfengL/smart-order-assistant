export async function request(path, options = {}) {
  const token = sessionStorage.getItem('orderly-token')
  const response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    if (response.status === 401) { sessionStorage.removeItem('orderly-token'); window.dispatchEvent(new Event('auth-expired')) }
    throw new Error(typeof data.detail === 'string' ? data.detail : `请求失败 (${response.status})`)
  }
  return response
}
export async function json(path, options) { return (await request(path, options)).json() }
export async function stream(path, message, onEvent, signal) {
  const response = await request(path, { method: 'POST', body: JSON.stringify({ message }), signal })
  const reader = response.body.getReader(), decoder = new TextDecoder()
  let pending = '', completed = false
  function consume(block) {
    const lines = block.split('\n'), event = lines.find(l => l.startsWith('event: '))?.slice(7)
    const data = lines.filter(l => l.startsWith('data: ')).map(l => l.slice(6)).join('\n')
    if (event && data) { if (event === 'done') completed = true; onEvent(event, JSON.parse(data)) }
  }
  try {
    while (true) {
      const { value, done } = await reader.read()
      pending += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      let boundary
      while ((boundary = pending.indexOf('\n\n')) >= 0) { consume(pending.slice(0, boundary)); pending = pending.slice(boundary + 2) }
      if (done) break
    }
    if (pending.trim()) consume(pending)
    if (!completed) throw new Error('连接中断或回答生成失败，请重试')
  } finally { reader.releaseLock() }
}

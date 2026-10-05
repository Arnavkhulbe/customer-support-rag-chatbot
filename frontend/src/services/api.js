const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Send a customer question to the RAG backend.
 * Resolves with { answer, sources, score } or throws an Error with a readable message.
 */
export async function sendQuestion(question, signal) {
  let response
  try {
    response = await fetch(`${API_URL}/api/v1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error('Cannot reach the support server. Is the backend running?')
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    try {
      const body = await response.json()
      if (body && typeof body.detail === 'string') message = body.detail
    } catch {
      // response had no JSON body — keep the generic message
    }
    throw new Error(message)
  }

  return response.json()
}

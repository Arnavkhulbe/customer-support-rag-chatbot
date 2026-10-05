import { useCallback, useEffect, useRef, useState } from 'react'
import ChatWindow from './components/ChatWindow/ChatWindow.jsx'
import ChatInput from './components/ChatInput/ChatInput.jsx'
import { sendQuestion } from './services/api.js'

const SUGGESTED_QUESTIONS = [
  'How long does delivery take?',
  'Can I return an item after 5 days?',
  'How long does a refund take?',
  'Can I exchange my product?',
  'How can I cancel my order?',
]

const WELCOME_MESSAGE = {
  id: 0,
  role: 'assistant',
  content:
    "Hello! 👋 I'm ShopSphere's AI support assistant. Ask me anything about orders, shipping, returns, exchanges, payments or refunds — I answer straight from our official policy documents.",
}

let nextMessageId = 1
const makeMessage = (role, content, extra = {}) => ({
  id: nextMessageId++,
  role,
  content,
  ...extra,
})

const NEAR_BOTTOM_PX = 80

export default function App() {
  const [messages, setMessages] = useState([WELCOME_MESSAGE])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)

  // Stick-to-bottom auto-scroll.
  // - stickRef: auto-scroll is active while the user is at/near the bottom.
  // - suppressRef: ignore the single 'scroll' event caused by our own programmatic
  //   jump, so it is never mistaken for the user scrolling away.
  const stickRef = useRef(true)
  const suppressRef = useRef(false)

  const handleMessagesScroll = useCallback((event) => {
    if (suppressRef.current) {
      suppressRef.current = false
      return
    }
    const el = event.currentTarget
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    stickRef.current = distanceFromBottom < NEAR_BOTTOM_PX
  }, [])

  const scrollToBottom = useCallback(() => {
    if (!stickRef.current) return
    const el = messagesEndRef.current
    if (!el) return
    // Instant jump: smooth scrolling races with response rendering and its own
    // scroll events would flip the stickiness flag mid-animation.
    suppressRef.current = true
    el.scrollIntoView({ block: 'end', behavior: 'instant' })
  }, [])

  // Runs after every render commit (new message, typing indicator, sources),
  // so the newest message is always scrolled into view when auto-scroll is on.
  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading, scrollToBottom])

  const askQuestion = useCallback(
    async (question) => {
      const trimmed = question.trim()
      if (!trimmed || isLoading) return

      stickRef.current = true // a new question always re-engages auto-scroll
      setMessages((prev) => [...prev, makeMessage('user', trimmed)])
      setIsLoading(true)

      try {
        const data = await sendQuestion(trimmed)
        setMessages((prev) => [
          ...prev,
          makeMessage('assistant', data.answer, {
            sources: data.sources ?? [],
            score: data.score ?? null,
          }),
        ])
      } catch (err) {
        if (err?.name === 'AbortError') return
        // Keep the UI alive: show the failure as an assistant-side error bubble.
        setMessages((prev) => [
          ...prev,
          makeMessage('assistant', 'Sorry, something went wrong. Please try again.', {
            isError: true,
          }),
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading],
  )

  const handleSuggestionClick = useCallback(
    (question) => {
      if (!isLoading) askQuestion(question)
    },
    [askQuestion, isLoading],
  )

  const showSuggestions = messages.length <= 1 && !isLoading

  return (
    <div className="app-shell">
      <main className="chat-card" aria-label="ShopSphere AI customer support chat">
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          messagesEndRef={messagesEndRef}
          onMessagesScroll={handleMessagesScroll}
          onSuggestionClick={handleSuggestionClick}
          suggestedQuestions={SUGGESTED_QUESTIONS}
          showSuggestions={showSuggestions}
        />
        <ChatInput onSend={askQuestion} disabled={isLoading} />
      </main>
      <p className="app-footer">
        Answers are generated from ShopSphere policy documents via retrieval-augmented generation.
        AI responses may contain mistakes — verify important details with support@shopsphere.example.
      </p>
    </div>
  )
}

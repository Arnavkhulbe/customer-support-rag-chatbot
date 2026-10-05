export default function TypingIndicator() {
  return (
    <div className="message-row message-row--assistant">
      <span className="message-avatar" aria-hidden="true">🤖</span>
      <div className="message-bubble message-bubble--typing">
        <span className="typing-text">AI is thinking</span>
        <span className="typing-dots" aria-hidden="true">
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </span>
      </div>
    </div>
  )
}

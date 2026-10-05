import MessageBubble from '../MessageBubble/MessageBubble.jsx'
import TypingIndicator from '../TypingIndicator/TypingIndicator.jsx'

export default function ChatWindow({
  messages,
  isLoading,
  messagesEndRef,
  onMessagesScroll,
  onSuggestionClick,
  suggestedQuestions,
  showSuggestions,
}) {
  return (
    <section className="chat-window">
      <header className="chat-header">
        <div className="brand">
          <span className="brand-logo" aria-hidden="true">🛍️</span>
          <div className="brand-text">
            <h1>ShopSphere</h1>
            <p>AI Customer Support</p>
          </div>
        </div>
        <span className="status-badge" role="status">
          <span className="status-dot" aria-hidden="true" />
          Online
        </span>
      </header>

      <div className="messages" role="log" aria-live="polite" onScroll={onMessagesScroll}>
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && <TypingIndicator />}

        {showSuggestions && (
          <div className="suggestions">
            <p className="suggestions-title">Try asking:</p>
            <div className="suggestions-list">
              {suggestedQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  className="suggestion-chip"
                  onClick={() => onSuggestionClick(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </section>
  )
}

import Markdown from 'react-markdown'
import SourceCard from '../SourceCard/SourceCard.jsx'

export default function MessageBubble({ message }) {
  const { role, content, sources, score, isError } = message
  const isUser = role === 'user'

  return (
    <div className={`message-row ${isUser ? 'message-row--user' : 'message-row--assistant'}`}>
      <span className="message-avatar" aria-hidden="true">
        {isUser ? '👤' : '🤖'}
      </span>
      <div className={`message-bubble ${isError ? 'message-bubble--error' : ''}`}>
        {isUser ? (
          // User messages are rendered as plain text.
          <p className="message-content">{content}</p>
        ) : (
          // Assistant messages are Markdown: **bold**, *italics*, lists…
          // Renders as elements (never raw **asterisks**).
          <Markdown className="message-content">{content}</Markdown>
        )}
        {!isUser && !isError && sources && sources.length > 0 && (
          <div className="sources">
            <p className="sources-title">Sources</p>
            {sources.map((source, index) => (
              <SourceCard
                key={`${source.document}-${source.page}-${index}`}
                document={source.document}
                page={source.page}
                score={source.score}
              />
            ))}
            {typeof score === 'number' && (
              <p className="sources-score" title="Best cosine similarity score of the retrieved chunks">
                relevance: {(score * 100).toFixed(0)}%
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

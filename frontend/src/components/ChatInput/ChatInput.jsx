import { forwardRef, useState } from 'react'

const MAX_LENGTH = 1000

export default forwardRef(function ChatInput({ onSend, disabled }, ref) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
    // Shift + Enter falls through and inserts a newline.
  }

  return (
    <footer className="chat-input">
      <textarea
        ref={ref}
        value={value}
        rows={1}
        maxLength={MAX_LENGTH}
        placeholder="Ask about returns, refunds, shipping…"
        aria-label="Your question"
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <button
        type="button"
        className="send-button"
        onClick={submit}
        disabled={disabled || !value.trim()}
        aria-label="Send message"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M3.4 20.4l17.45-7.48a1 1 0 000-1.84L3.4 3.6a.993.993 0 00-1.39.91L2 9.12c0 .5.37.93.87.99L17 12 2.87 13.88c-.5.07-.87.5-.87 1l.01 4.61c0 .71.73 1.2 1.39.91z"
            fill="currentColor"
          />
        </svg>
      </button>
    </footer>
  )
})

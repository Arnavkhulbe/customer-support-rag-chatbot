const DOCUMENT_LABELS = {
  'return-policy.pdf': 'Return Policy',
  'exchange-policy.pdf': 'Exchange Policy',
  'payment-refund-policy.pdf': 'Payment & Refund Policy',
  'shipping-delivery.pdf': 'Shipping & Delivery',
  'orders-account-help.pdf': 'Orders & Account Help',
}

export default function SourceCard({ document, page, score }) {
  const label = DOCUMENT_LABELS[document] || document.replace(/\.pdf$/i, '')

  return (
    <div className="source-card" title={`Source: ${document}, page ${page}`}>
      <span className="source-icon" aria-hidden="true">📄</span>
      <span className="source-name">{label}</span>
      <span className="source-page">Page {page}</span>
      {typeof score === 'number' && (
        <span className="source-score" title="Cosine similarity score">
          {(score * 100).toFixed(0)}%
        </span>
      )}
    </div>
  )
}

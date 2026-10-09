import { AlertTriangle, ShieldCheck } from 'lucide-react'
import type { DocumentRecord } from '../../types/api'
import { Badge } from '../ui/Badge'

function Highlighted({ text, quote }: { text: string; quote: string | null }) {
  const i = quote ? text.indexOf(quote) : -1
  if (!quote || i < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded-sm bg-accent/25 px-0.5 text-fg">{quote}</mark>
      {text.slice(i + quote.length)}
    </>
  )
}

/**
 * The bounded excerpt that was sent to the model, verbatim, with the model's
 * evidence quote highlighted. Visually distinct from extracted values (monospace, quote rail).
 */
export function EvidenceBlock({ doc }: { doc: DocumentRecord }) {
  const c = doc.classification
  const quote = c?.evidence_quote ?? null
  const found = quote ? doc.excerpt.includes(quote) : false
  return (
    <figure className="rounded-md border border-line bg-bg/60">
      <figcaption className="flex items-center justify-between gap-2 border-b border-line px-2.5 py-1.5 text-2xs text-fg-subtle">
        <span>Excerpt sent to the local model</span>
        {quote &&
          (c?.evidence_verified && found ? (
            <Badge tone="success" icon={ShieldCheck} title="The backend confirmed the quote occurs in the document text.">
              Evidence verified
            </Badge>
          ) : (
            <Badge tone="warning" icon={AlertTriangle} title="The quote the model gave could not be found in the document text.">
              Evidence not found
            </Badge>
          ))}
      </figcaption>
      <blockquote className="m-0 max-h-56 overflow-auto whitespace-pre-wrap border-l-2 border-line-strong px-2.5 py-2 font-mono text-xs leading-5 text-fg-muted">
        {doc.excerpt ? <Highlighted text={doc.excerpt} quote={found ? quote : null} /> : <span className="italic">No text could be extracted.</span>}
      </blockquote>
      {quote && !found && (
        <div className="border-t border-line px-2.5 py-1.5 text-2xs text-fg-subtle">
          Model's quote: <span className="font-mono text-fg-muted">“{quote}”</span>
        </div>
      )}
    </figure>
  )
}

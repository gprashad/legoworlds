import { useState } from 'react'

interface FeedbackFormProps {
  onSubmit: (feedback: string) => void
  disabled: boolean
}

export function FeedbackForm({ onSubmit, disabled }: FeedbackFormProps) {
  const [feedback, setFeedback] = useState('')

  return (
    <div className="bg-surface rounded-xl border border-border p-5 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
        Want changes?
      </h3>
      <textarea
        value={feedback}
        onChange={e => setFeedback(e.target.value)}
        placeholder="Tell us what to change... (e.g. 'Make the dragon funnier' or 'Add more dialogue for the wizard')"
        rows={3}
        className="w-full bg-surface-elevated border border-border rounded-lg px-4 py-3 text-text-primary placeholder:text-text-secondary/50 resize-y text-sm focus:outline-none focus:border-accent transition-colors"
      />
      <button
        onClick={() => { onSubmit(feedback); setFeedback('') }}
        disabled={disabled || !feedback.trim()}
        className="px-5 py-2 bg-review text-white rounded-lg font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Revise Script
      </button>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import type { StructuredDescription } from '../../types/shotlist'

interface DescriptionFormProps {
  value: StructuredDescription
  onChange: (value: StructuredDescription) => void
}

const MOODS = ['action', 'comedy', 'drama', 'mystery', 'adventure', 'thriller']

export function DescriptionForm({ value, onChange }: DescriptionFormProps) {
  const [local, setLocal] = useState<StructuredDescription>(value)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setLocal(value)
  }, [value])

  const update = (key: keyof StructuredDescription, val: string) => {
    const next = { ...local, [key]: val }
    setLocal(next)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => onChange(next), 500)
  }

  const charCount = (local.what_happens || '').length + (local.one_liner || '').length

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-1">
          The Brief
        </h2>
        <p className="text-xs text-text-secondary">
          Your words become the director's notes. Claude will turn this into a cinematic trailer.
        </p>
      </div>

      {/* One liner */}
      <div>
        <label className="block text-xs text-text-secondary mb-1">🎬 What's this movie about? (one sentence)</label>
        <input
          type="text"
          value={local.one_liner || ''}
          onChange={e => update('one_liner', e.target.value)}
          placeholder="e.g. A bank robbery that goes sideways"
          className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-text-primary text-sm focus:outline-none focus:border-accent transition-colors"
        />
      </div>

      {/* Characters */}
      <div>
        <label className="block text-xs text-text-secondary mb-1">
          👥 Who's in it? (each character on a new line)
        </label>
        <textarea
          value={local.characters || ''}
          onChange={e => update('characters', e.target.value)}
          placeholder={`The bank robber - greedy, sneaky\nThe brave cop - fearless\nRandom citizen - clueless`}
          rows={4}
          className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-text-primary text-sm focus:outline-none focus:border-accent transition-colors resize-y"
        />
      </div>

      {/* What happens */}
      <div>
        <label className="block text-xs text-text-secondary mb-1">
          📖 What happens? (2-4 sentences)
        </label>
        <textarea
          value={local.what_happens || ''}
          onChange={e => update('what_happens', e.target.value)}
          placeholder="The robber grabs the money and runs. The cop chases him. They crash into the citizen. The robber trips and drops the money."
          rows={4}
          className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-text-primary text-sm focus:outline-none focus:border-accent transition-colors resize-y"
        />
      </div>

      {/* Mood */}
      <div>
        <label className="block text-xs text-text-secondary mb-2">🎭 Mood</label>
        <div className="flex flex-wrap gap-2">
          {MOODS.map(m => (
            <button
              key={m}
              type="button"
              onClick={() => update('mood', m)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                local.mood === m
                  ? 'bg-accent text-black'
                  : 'bg-surface-elevated text-text-secondary border border-border hover:border-accent'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <p className="text-xs text-text-secondary">
        {charCount > 0 ? `${charCount} characters written` : 'Fill in the brief above'}
      </p>
    </div>
  )
}

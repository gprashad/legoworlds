import { useEffect, useRef, useState } from 'react'

interface BackstoryEditorProps {
  value: string
  onChange: (value: string) => void
}

export function BackstoryEditor({ value, onChange }: BackstoryEditorProps) {
  const [localValue, setLocalValue] = useState(value)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setLocalValue(value)
  }, [value])

  const handleChange = (newValue: string) => {
    setLocalValue(newValue)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => onChange(newValue), 500)
  }

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-text-primary">Backstory</label>
      <textarea
        value={localValue}
        onChange={e => handleChange(e.target.value)}
        placeholder="Tell the story of your scene... Describe who the characters are, what's happening, and what's about to happen next!"
        rows={5}
        className="w-full bg-surface-elevated border border-border rounded-xl px-4 py-3 text-text-primary placeholder:text-text-secondary/50 resize-y focus:outline-none focus:border-accent transition-colors"
      />
      <div className="flex justify-between text-xs text-text-secondary">
        <span>
          {localValue.length < 20 && localValue.length > 0
            ? `${20 - localValue.length} more characters needed`
            : '\u00A0'}
        </span>
        <span>{localValue.length} characters</span>
      </div>
    </div>
  )
}

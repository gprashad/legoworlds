import { useCallback, useRef, useState } from 'react'

interface MediaUploaderProps {
  onFilesSelected: (files: File[]) => void
  uploading: boolean
}

export function MediaUploader({ onFilesSelected, uploading }: MediaUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = useCallback((fileList: FileList) => {
    const files = Array.from(fileList).filter(f =>
      f.type.startsWith('image/') || f.type.startsWith('video/')
    )
    if (files.length > 0) onFilesSelected(files)
  }, [onFilesSelected])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }, [handleFiles])

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`
        flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed cursor-pointer transition-colors
        ${dragOver ? 'border-accent bg-accent/10' : 'border-border hover:border-text-secondary'}
        ${uploading ? 'opacity-50 pointer-events-none' : ''}
      `}
    >
      <span className="text-3xl">{uploading ? '⏳' : '+'}</span>
      <span className="text-sm text-text-secondary">
        {uploading ? 'Uploading...' : 'Drop photos here or click to add'}
      </span>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,video/*"
        multiple
        className="hidden"
        onChange={e => e.target.files && handleFiles(e.target.files)}
      />
    </div>
  )
}

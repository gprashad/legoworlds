import { useCallback, useRef, useState } from 'react'

interface MediaUploaderProps {
  onFilesSelected: (files: File[]) => void
  uploading: boolean
}

export function MediaUploader({ onFilesSelected, uploading }: MediaUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = useCallback((fileList: FileList) => {
    const files = Array.from(fileList).filter(f => {
      const type = f.type.toLowerCase()
      const name = f.name.toLowerCase()
      // Accept by MIME type
      if (type.startsWith('image/') || type.startsWith('video/')) return true
      // Fallback: accept by extension (iOS sometimes has empty type)
      if (name.endsWith('.jpg') || name.endsWith('.jpeg') || name.endsWith('.png') ||
          name.endsWith('.webp') || name.endsWith('.gif') || name.endsWith('.heic') ||
          name.endsWith('.mp4') || name.endsWith('.mov') || name.endsWith('.m4v') ||
          name.endsWith('.webm')) return true
      return false
    })
    if (files.length > 0) onFilesSelected(files)
  }, [onFilesSelected])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }, [handleFiles])

  const handleClick = () => {
    // Reset input so re-selecting the same file triggers onChange
    if (inputRef.current) inputRef.current.value = ''
    inputRef.current?.click()
  }

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={handleClick}
      className={`
        flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed cursor-pointer transition-colors
        ${dragOver ? 'border-accent bg-accent/10' : 'border-border hover:border-text-secondary'}
        ${uploading ? 'opacity-50 pointer-events-none' : ''}
      `}
    >
      <span className="text-3xl">{uploading ? '⏳' : '+'}</span>
      <span className="text-sm text-text-secondary">
        {uploading ? 'Uploading...' : 'Add photos or videos'}
      </span>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,video/*,.mov,.mp4,.m4v,.heic"
        multiple
        capture={undefined}
        className="hidden"
        onChange={e => {
          if (e.target.files && e.target.files.length > 0) handleFiles(e.target.files)
        }}
      />
    </div>
  )
}

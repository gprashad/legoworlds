import { useCallback, useRef, useState } from 'react'

interface MediaUploaderProps {
  onFilesSelected: (files: File[]) => void
  uploading: boolean
  uploadProgress?: number
  uploadFileName?: string
}

export function MediaUploader({ onFilesSelected, uploading, uploadProgress = 0, uploadFileName = '' }: MediaUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = useCallback((fileList: FileList) => {
    const files = Array.from(fileList).filter(f => {
      const type = f.type.toLowerCase()
      const name = f.name.toLowerCase()
      if (type.startsWith('image/') || type.startsWith('video/')) return true
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
    if (inputRef.current) inputRef.current.value = ''
    inputRef.current?.click()
  }

  // Show progress bar during upload
  if (uploading) {
    return (
      <div className="rounded-xl border-2 border-accent/30 bg-accent/5 p-5 space-y-3">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-accent border-t-transparent flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-text-primary font-medium truncate">
              Uploading {uploadFileName || 'file'}...
            </p>
            <p className="text-xs text-text-secondary">
              {uploadProgress < 100 ? `${uploadProgress}% uploaded` : 'Processing...'}
            </p>
          </div>
          <span className="text-sm font-semibold text-accent">{uploadProgress}%</span>
        </div>
        <div className="w-full bg-surface-elevated rounded-full h-2.5 overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all duration-300"
            style={{ width: `${Math.max(uploadProgress, 2)}%` }}
          />
        </div>
      </div>
    )
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
      `}
    >
      <span className="text-3xl">+</span>
      <span className="text-sm text-text-secondary">Add photos or videos</span>
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

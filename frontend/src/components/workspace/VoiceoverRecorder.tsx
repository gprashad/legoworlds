import { useState, useRef, useEffect, useCallback } from 'react'
import { supabase } from '../../config/supabase'

interface VoiceoverRecorderProps {
  sceneId: string
  existingUrl: string | null
  onRecorded: (url: string) => void
  onRemoved: () => void
}

export function VoiceoverRecorder({ sceneId, existingUrl, onRecorded, onRemoved }: VoiceoverRecorderProps) {
  const [recording, setRecording] = useState(false)
  const [audioUrl, setAudioUrl] = useState<string | null>(existingUrl)
  const [duration, setDuration] = useState(0)
  const [uploading, setUploading] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animFrameRef = useRef<number>(0)

  useEffect(() => {
    setAudioUrl(existingUrl)
  }, [existingUrl])

  const drawWaveform = useCallback(() => {
    const analyser = analyserRef.current
    const canvas = canvasRef.current
    if (!analyser || !canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const data = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteTimeDomainData(data)

    ctx.fillStyle = '#2A2A2A'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    ctx.lineWidth = 2
    ctx.strokeStyle = '#E3000B'
    ctx.beginPath()

    const sliceWidth = canvas.width / data.length
    let x = 0
    for (let i = 0; i < data.length; i++) {
      const v = data[i] / 128.0
      const y = (v * canvas.height) / 2
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
      x += sliceWidth
    }
    ctx.lineTo(canvas.width, canvas.height / 2)
    ctx.stroke()

    animFrameRef.current = requestAnimationFrame(drawWaveform)
  }, [])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      // Set up analyser for waveform
      const audioCtx = new AudioContext()
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      analyserRef.current = analyser

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        cancelAnimationFrame(animFrameRef.current)

        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        await uploadVoiceover(blob)
      }

      mediaRecorder.start(250)
      setRecording(true)
      setDuration(0)

      timerRef.current = setInterval(() => {
        setDuration(d => {
          if (d >= 60) {
            mediaRecorderRef.current?.stop()
            if (timerRef.current) clearInterval(timerRef.current)
            setRecording(false)
            return 60
          }
          return d + 1
        })
      }, 1000)

      drawWaveform()
    } catch {
      // Microphone permission denied or not available
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    if (timerRef.current) clearInterval(timerRef.current)
    setRecording(false)
  }

  const uploadVoiceover = async (blob: Blob) => {
    setUploading(true)
    const storagePath = `scenes/${sceneId}/input/voiceover.webm`

    const { error } = await supabase.storage
      .from('legoworlds')
      .upload(storagePath, blob, { contentType: 'audio/webm', upsert: true })

    if (!error) {
      const { data: { publicUrl } } = supabase.storage
        .from('legoworlds')
        .getPublicUrl(storagePath)
      setAudioUrl(publicUrl)
      onRecorded(publicUrl)
    }
    setUploading(false)
  }

  const removeVoiceover = async () => {
    const storagePath = `scenes/${sceneId}/input/voiceover.webm`
    await supabase.storage.from('legoworlds').remove([storagePath])
    setAudioUrl(null)
    setDuration(0)
    onRemoved()
  }

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-text-primary">Voiceover</h3>
      <p className="text-xs text-text-secondary">
        Record yourself talking about what you built and what's happening in your scene.
      </p>

      {/* Waveform canvas — visible during recording */}
      {recording && (
        <canvas
          ref={canvasRef}
          width={400}
          height={60}
          className="w-full h-15 rounded-lg"
        />
      )}

      {/* Playback */}
      {audioUrl && !recording && (
        <div className="flex items-center gap-3">
          <audio src={audioUrl} controls className="flex-1 h-10" />
          <button
            onClick={removeVoiceover}
            className="text-xs text-error hover:underline"
          >
            Remove
          </button>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-3">
        {!recording && !uploading && (
          <button
            onClick={startRecording}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-hover transition-colors"
          >
            <span className="w-3 h-3 rounded-full bg-white" />
            {audioUrl ? 'Re-record' : 'Record Voiceover'}
          </button>
        )}
        {recording && (
          <>
            <button
              onClick={stopRecording}
              className="flex items-center gap-2 px-4 py-2 bg-error text-white rounded-lg text-sm font-medium animate-pulse"
            >
              <span className="w-3 h-3 rounded-sm bg-white" />
              Stop
            </button>
            <span className="text-sm text-text-secondary">
              {formatTime(duration)} / 1:00
            </span>
          </>
        )}
        {uploading && (
          <span className="text-sm text-text-secondary">Uploading...</span>
        )}
      </div>
    </div>
  )
}

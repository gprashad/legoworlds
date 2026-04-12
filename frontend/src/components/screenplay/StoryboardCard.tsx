import type { ScreenplayScene } from '../../types/screenplay'

interface StoryboardCardProps {
  scene: ScreenplayScene
}

export function StoryboardCard({ scene }: StoryboardCardProps) {
  return (
    <div className="bg-surface rounded-xl border border-border p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-text-primary">
          Scene {scene.scene_number}: "{scene.title}"
        </h3>
        <span className="text-xs text-text-secondary bg-surface-elevated px-2 py-1 rounded-full">
          {scene.duration_seconds}s
        </span>
      </div>

      <div className="text-sm text-text-secondary space-y-1">
        <p>📷 {scene.camera.angle}, {scene.camera.movement}</p>
      </div>

      <p className="text-sm text-text-primary leading-relaxed">{scene.action}</p>

      {scene.dialogue.length > 0 && (
        <div className="space-y-2 pl-3 border-l-2 border-accent/30">
          {scene.dialogue.map((line, i) => (
            <div key={i} className="text-sm">
              <span className="font-medium text-accent">
                {line.character.replace(/_/g, ' ')}
              </span>
              <span className="text-text-secondary italic"> ({line.emotion})</span>
              <p className="text-text-primary font-mono mt-0.5">"{line.line}"</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
        {scene.sound_effects.map((sfx, i) => (
          <span key={i} className="bg-surface-elevated px-2 py-1 rounded-full">
            🔊 {sfx}
          </span>
        ))}
        <span className="bg-surface-elevated px-2 py-1 rounded-full">
          🎵 {scene.music_mood}
        </span>
      </div>
    </div>
  )
}

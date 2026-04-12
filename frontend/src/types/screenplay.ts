export interface DialogueLine {
  character: string
  line: string
  emotion: string
}

export interface CameraDirection {
  angle: string
  movement: string
  reference_photo: string
}

export interface ScreenplayScene {
  scene_number: number
  title: string
  duration_seconds: number
  location: string
  camera: CameraDirection
  action: string
  dialogue: DialogueLine[]
  sound_effects: string[]
  music_mood: string
}

export interface Screenplay {
  title: string
  total_scenes: number
  estimated_duration_seconds: number
  scenes: ScreenplayScene[]
  narrator_intro: string
  narrator_outro: string
  credits: {
    directed_by: string
    built_by: string
    produced_by: string
  }
}

export interface PipelineJob {
  id: string
  scene_id: string
  status: string
  current_stage: string | null
  progress_pct: number
  stages_completed: string[]
  error: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface PipelineStatus {
  job: PipelineJob | null
  scene_status: string
  has_screenplay: boolean
}

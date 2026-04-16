export interface SceneMedia {
  id: string
  scene_id: string
  file_url: string
  file_type: 'photo' | 'video'
  file_name: string | null
  file_size_bytes: number | null
  sort_order: number
  source: string
  created_at: string
}

export interface Scene {
  id: string
  user_id: string
  title: string
  backstory: string | null
  status: SceneStatus
  director_name: string | null
  movie_style: string | null
  music_mood: string | null
  scene_bible: Record<string, unknown> | null
  screenplay: Record<string, unknown> | null
  shot_list: Record<string, unknown> | null
  shot_list_version?: number
  structured_description: Record<string, unknown> | null
  screenplay_feedback: string | null
  screenplay_version: number
  music_track?: string | null
  voiceover_url: string | null
  final_video_url: string | null
  final_video_duration_seconds: number | null
  published_platforms: string[] | null
  created_at: string
  updated_at: string
  media: SceneMedia[]
}

export type SceneStatus =
  | 'draft'
  | 'ready'
  | 'analyzing'
  | 'screenplay_review'
  | 'approved'
  | 'producing'
  | 'assembling'
  | 'complete'
  | 'published'
  | 'failed'

export interface SceneCreate {
  title?: string
  backstory?: string
  director_name?: string
  movie_style?: string
}

export interface SceneUpdate {
  title?: string
  backstory?: string
  director_name?: string
  movie_style?: string
  music_mood?: string
  structured_description?: Record<string, unknown>
}

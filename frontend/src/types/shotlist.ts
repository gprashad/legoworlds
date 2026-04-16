export interface NarratorLine {
  time_seconds: number
  line: string
}

export interface Shot {
  shot_number: number
  duration_seconds: number
  type: string
  description: string
  reference_photo_index: number
  subject: string
  motion: string
  camera: string
  sfx_keyword: string | null
}

export interface ShotList {
  title: string
  tagline: string
  genre: string
  mood: string
  total_duration_seconds: number
  music_mood: string
  narrator_lines: NarratorLine[]
  shots: Shot[]
}

export interface StructuredDescription {
  title?: string
  one_liner?: string
  characters?: string
  what_happens?: string
  mood?: string
}

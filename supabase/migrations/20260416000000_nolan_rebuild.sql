-- Nolan rebuild: structured description + shot list replaces backstory + screenplay

-- Add structured description (kid's brief: title, characters, what_happens, mood)
ALTER TABLE scenes ADD COLUMN IF NOT EXISTS structured_description jsonb;

-- Add shot_list (replaces screenplay with trailer-style shot list + narrator lines)
ALTER TABLE scenes ADD COLUMN IF NOT EXISTS shot_list jsonb;

-- Add shot_list_version (track revisions)
ALTER TABLE scenes ADD COLUMN IF NOT EXISTS shot_list_version int DEFAULT 0;

-- Add music_track (which bundled music track was used)
ALTER TABLE scenes ADD COLUMN IF NOT EXISTS music_track text;

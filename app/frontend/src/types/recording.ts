export interface RecordingSettings {
  enabled: boolean;
  filename_template: string;
  filename_preset?: string;
  default_quality: string;
  use_chapters: boolean;
  use_category_as_chapter_title?: boolean; // Neue Eigenschaft hinzufügen
  cleanup_policy?: CleanupPolicy; // New property for cleanup policy
}

export interface StreamerRecordingSettings {
  streamer_id: number;
  username: string;
  enabled: boolean;
  quality?: string;
  custom_filename?: string;
  profile_image_url?: string;
  max_streams?: number; // Maximum number of streams to keep for this streamer
  cleanup_policy?: CleanupPolicy; // New property for streamer-specific cleanup policy
  use_global_cleanup_policy?: boolean; // Use global cleanup policy or streamer-specific (default: true)
}

// New type for advanced cleanup policies
export interface CleanupPolicy {
  type: CleanupPolicyType;
  threshold: number;
  preserve_favorites: boolean;
  preserve_categories: string[];
  preserve_timeframe?: PreserveTimeframe; // Made optional to simplify
}

export enum CleanupPolicyType {
  COUNT = 'count',       // Limit by number of recordings
  SIZE = 'size',         // Limit by total size (in GB)
  AGE = 'age',           // Limit by age (in days)
  CUSTOM = 'custom'      // Custom policy (combination of the above)
}

export interface PreserveTimeframe {
  start_date: string;   // ISO date string
  end_date: string;     // ISO date string 
  weekdays: number[];   // 0-6 (Sunday-Saturday)
  timeOfDay: {
    start: string;       // HH:MM format
    end: string;         // HH:MM format
  };
}

export interface ActiveRecording {
  id: number;              // recording_id
  stream_id: number;
  streamer_id: number;
  streamer_name: string;
  title: string;
  started_at: string;
  file_path: string;
  status: string;
  duration: number;
  // Legacy fields for backwards compatibility
  output_path?: string;
  quality?: string;
}

export const QUALITY_OPTIONS = [
  { value: "best", label: "Best Available" },
  { value: "1080p60", label: "1080p (60 fps)" },
  { value: "1080p", label: "1080p (30 fps)" },
  { value: "720p60", label: "720p (60 fps)" },
  { value: "720p", label: "720p (30 fps)" },
  { value: "480p", label: "480p" },
  { value: "360p", label: "360p" },
  { value: "160p", label: "160p" },
  { value: "audio_only", label: "Audio Only" }
];

export const FILENAME_VARIABLES = [
  { key: "streamer", description: "Streamer username" },
  { key: "title", description: "Stream title" },
  { key: "game", description: "Game/category name" },
  { key: "twitch_id", description: "Twitch ID" },
  { key: "year", description: "Year (YYYY)" },
  { key: "month", description: "Month (MM)" },
  { key: "day", description: "Day (DD)" },
  { key: "hour", description: "Hour (HH)" },
  { key: "minute", description: "Minute (MM)" },
  { key: "second", description: "Second (SS)" },
  { key: "timestamp", description: "Timestamp (YYYYMMDD_HHMMSS)" },
  { key: "datetime", description: "Formatted datetime (YYYY-MM-DD_HH-MM-SS)" },
  { key: "id", description: "Stream ID" },
  { key: "season", description: "Season format (S2024-01)" },
  { key: "episode", description: "Episode number (E01, E02, ...)" },
  { key: "unique", description: "Unique identifier" }
];

export interface FilenamePreset {
  value: string;
  label: string;
  description: string;
}

export const FILENAME_PRESETS: FilenamePreset[] = [
  { 
    value: "default", 
    label: "Default", 
    description: "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}"
  },
  { 
    value: "plex", 
    label: "Plex/Emby/Jellyfin", 
    description: "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}"
  },
  { 
    value: "emby", 
    label: "Emby Alternative", 
    description: "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}"
  },
  { 
    value: "jellyfin", 
    label: "Jellyfin Alternative", 
    description: "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}"
  },
  { 
    value: "kodi", 
    label: "Kodi", 
    description: "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}"
  },
  { 
    value: "chronological", 
    label: "Chronological", 
    description: "{year}/{month}/{day}/{streamer} - E{episode:02d} - {title} - {hour}-{minute}"
  }
];

export interface RecordingSettings {
  enabled: boolean;
  output_directory: string;
  filename_template: string;
  filename_preset?: string;
  default_quality: string;
  use_chapters: boolean;
  use_category_as_chapter_title?: boolean; // Neue Eigenschaft hinzufügen
}
export interface StreamerRecordingSettings {
  streamer_id: number;
  username: string;
  enabled: boolean;
  quality?: string;
  custom_filename?: string;
  profile_image_url?: string;
}
export interface ActiveRecording {
  streamer_id: number;
  streamer_name: string;
  started_at: string;
  duration: number;
  output_path: string;
  quality: string;
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
  { key: "season", description: "Season format (S2024-01)" }
];

export const FILENAME_PRESETS = [
  { 
    value: "default", 
    label: "Default", 
    description: "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}"
  },
  { 
    value: "plex", 
    label: "Plex-Friendly", 
    description: "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{day} - {title}"
  },
  { 
    value: "emby", 
    label: "Emby-Friendly", 
    description: "{streamer}/S{year}{month}/{streamer} - S{year}{month}E{day} - {title}"
  },
  { 
    value: "jellyfin", 
    label: "Jellyfin-Friendly", 
    description: "{streamer}/Season {year}{month}/{streamer} - {year}.{month}.{day} - {title}"
  },
  { 
    value: "kodi", 
    label: "Kodi-Friendly", 
    description: "{streamer}/Season {year}-{month}/{streamer} - s{year}e{month}{day} - {title}"
  },
  { 
    value: "chronological", 
    label: "Chronological", 
    description: "{year}/{month}/{day}/{streamer} - {title} - {hour}-{minute}"
  }
];

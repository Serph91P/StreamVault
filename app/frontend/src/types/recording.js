export var CleanupPolicyType;
(function (CleanupPolicyType) {
    CleanupPolicyType["COUNT"] = "count";
    CleanupPolicyType["SIZE"] = "size";
    CleanupPolicyType["AGE"] = "age";
    CleanupPolicyType["CUSTOM"] = "custom"; // Custom policy (combination of the above)
})(CleanupPolicyType || (CleanupPolicyType = {}));
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
export const FILENAME_PRESETS = [
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

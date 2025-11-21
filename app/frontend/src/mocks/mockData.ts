/**
 * Mock Data for Frontend Development
 * 
 * Use VITE_USE_MOCK_DATA=true in .env to enable mock mode
 * This allows testing all UI components without a running backend
 */

export const mockStreamers = [
  {
    id: 1,
    username: 'streamer_alpha',
    twitch_id: '12345',
    profile_image_url: 'https://static-cdn.jtvnw.net/jtv_user_pictures/2b1f0b6e-8b0c-4f3a-8b1a-1f0b6e8b0c4f-profile_image-300x300.png',
    is_live: true,
    is_recording: true,
    video_count: 42,
    title: 'Just Chatting with Chat!',
    category_name: 'Just Chatting',
    viewer_count: 1234,
    created_at: '2024-01-15T10:30:00Z',
    enabled: true
  },
  {
    id: 2,
    username: 'speedrunner_pro',
    twitch_id: '23456',
    profile_image_url: 'https://static-cdn.jtvnw.net/jtv_user_pictures/3c2f1c7f-9c1d-5g4b-9c2b-2g1c7f9c1d5g-profile_image-300x300.png',
    is_live: true,
    is_recording: false,
    video_count: 156,
    title: 'Ranked Climbing Session',
    category_name: 'Competitive Gaming',
    viewer_count: 5678,
    created_at: '2023-06-20T14:45:00Z',
    enabled: true
  },
  {
    id: 3,
    username: 'retro_gamer',
    twitch_id: '34567',
    profile_image_url: 'https://static-cdn.jtvnw.net/jtv_user_pictures/4d3g2d8g-0d2e-6h5c-0d3c-3h2d8g0d2e6h-profile_image-300x300.png',
    is_live: false,
    is_recording: false,
    video_count: 89,
    last_stream_title: 'Classic RPG Marathon',
    last_stream_category_name: 'Retro',
    last_stream_ended_at: '2025-11-19T22:30:00Z',
    created_at: '2024-03-10T08:00:00Z',
    enabled: true
  },
  {
    id: 4,
    username: 'casual_streamer',
    twitch_id: '45678',
    profile_image_url: 'https://static-cdn.jtvnw.net/jtv_user_pictures/5e4h3e9h-1e3f-7i6d-1e4d-4i3e9h1e3f7i-profile_image-300x300.png',
    is_live: false,
    is_recording: false,
    video_count: 23,
    last_stream_ended_at: '2025-11-15T18:00:00Z',
    created_at: '2024-08-05T12:00:00Z',
    enabled: true
  }
]

export const mockVideos = [
  {
    id: 1,
    streamer_id: 1,
    streamer_name: 'streamer_alpha',
    title: 'Morning Talk Show - Community Discussion',
    category_name: 'Just Chatting',
    duration: 2340, // 39 minutes in seconds
    file_size: 1024 * 1024 * 450, // 450 MB
    recorded_at: '2025-11-20T10:14:00Z',
    thumbnail_url: null,
    file_path: '/recordings/streamer_alpha/Season 2025-11/streamer_alpha - S202511E02 - Morning_Talk_Show.ts',
    viewer_count: 1200,
    has_chapters: true
  },
  {
    id: 2,
    streamer_id: 2,
    streamer_name: 'speedrunner_pro',
    title: 'Ranked Climbing Session - Road to Masters',
    category_name: 'Competitive Gaming',
    duration: 7200, // 2 hours
    file_size: 1024 * 1024 * 1200, // 1.2 GB
    recorded_at: '2025-11-19T18:30:00Z',
    thumbnail_url: null,
    file_path: '/recordings/speedrunner_pro/Season 2025-11/speedrunner_pro - S202511E15 - Ranked_Climbing.ts',
    viewer_count: 5500,
    has_chapters: true
  },
  {
    id: 3,
    streamer_id: 3,
    streamer_name: 'retro_gamer',
    title: 'Retro RPG Marathon - Classic Gaming Session',
    category_name: 'Retro',
    duration: 10800, // 3 hours
    file_size: 1024 * 1024 * 1800, // 1.8 GB
    recorded_at: '2025-11-18T20:00:00Z',
    thumbnail_url: null,
    file_path: '/recordings/herrmaximal/Season 2025-11/herrmaximal - S202511E08 - Retro_RPG_Marathon.ts',
    viewer_count: 890,
    has_chapters: false
  },
  {
    id: 4,
    streamer_id: 1,
    streamer_name: 'streamer_alpha',
    title: 'Morning Chill Stream - Coffee and Chat',
    category_name: 'Just Chatting',
    duration: 4200, // 70 minutes
    file_size: 1024 * 1024 * 680, // 680 MB
    recorded_at: '2025-11-17T08:00:00Z',
    thumbnail_url: null,
    file_path: '/recordings/streamer_alpha/Season 2025-11/streamer_alpha - S202511E01 - Morning_Chill_Stream.ts',
    viewer_count: 450,
    has_chapters: true
  },
  {
    id: 5,
    streamer_id: 2,
    streamer_name: 'speedrunner_pro',
    title: 'Speedrun Practice - Sub 30 Minute Attempts',
    category_name: 'Speedrunning',
    duration: 5400, // 90 minutes
    file_size: 1024 * 1024 * 900, // 900 MB
    recorded_at: '2025-11-16T14:30:00Z',
    thumbnail_url: null,
    file_path: '/recordings/speedrunner_pro/Season 2025-11/speedrunner_pro - S202511E12 - Speedrun_Practice.ts',
    viewer_count: 2300,
    has_chapters: false
  },
  {
    id: 6,
    streamer_id: 4,
    streamer_name: 'casual_streamer',
    title: 'Late Night Variety Stream - Viewer Games',
    category_name: 'Variety',
    duration: 6300, // 105 minutes
    file_size: 1024 * 1024 * 1050, // 1.05 GB
    recorded_at: '2025-11-15T22:00:00Z',
    thumbnail_url: null,
    file_path: '/recordings/casual_streamer/Season 2025-11/casual_streamer - S202511E03 - Late_Night_Variety.ts',
    viewer_count: 780,
    has_chapters: true
  },
  {
    id: 7,
    streamer_id: 3,
    streamer_name: 'retro_gamer',
    title: 'Indie Game Showcase - Hidden Gems',
    category_name: 'Indie Games',
    duration: 8100, // 135 minutes
    file_size: 1024 * 1024 * 1350, // 1.35 GB
    recorded_at: '2025-11-14T19:00:00Z',
    thumbnail_url: null,
    file_path: '/recordings/retro_gamer/Season 2025-11/retro_gamer - S202511E06 - Indie_Game_Showcase.ts',
    viewer_count: 1100,
    has_chapters: false
  },
  {
    id: 8,
    streamer_id: 1,
    streamer_name: 'streamer_alpha',
    title: 'Weekend Collab Stream - Special Guest',
    category_name: 'Just Chatting',
    duration: 9000, // 150 minutes
    file_size: 1024 * 1024 * 1500, // 1.5 GB
    recorded_at: '2025-11-13T16:00:00Z',
    thumbnail_url: null,
    file_path: '/recordings/streamer_alpha/Season 2025-11/streamer_alpha - S202511E00 - Weekend_Collab.ts',
    viewer_count: 3400,
    has_chapters: true
  },
  {
    id: 9,
    streamer_id: 2,
    streamer_name: 'speedrunner_pro',
    title: 'Ranked Grind - Competitive Gaming',
    category_name: 'Competitive',
    duration: 7800, // 130 minutes
    file_size: 1024 * 1024 * 1300, // 1.3 GB
    recorded_at: '2025-11-12T20:30:00Z',
    thumbnail_url: null,
    file_path: '/recordings/speedrunner_pro/Season 2025-11/speedrunner_pro - S202511E10 - Ranked_Grind.ts',
    viewer_count: 4200,
    has_chapters: true
  },
  {
    id: 10,
    streamer_id: 4,
    streamer_name: 'casual_streamer',
    title: 'Community Game Night - Jackbox Party',
    category_name: 'Party Games',
    duration: 5700, // 95 minutes
    file_size: 1024 * 1024 * 950, // 950 MB
    recorded_at: '2025-11-11T21:00:00Z',
    thumbnail_url: null,
    file_path: '/recordings/casual_streamer/Season 2025-11/casual_streamer - S202511E02 - Community_Game_Night.ts',
    viewer_count: 620,
    has_chapters: false
  },
  {
    id: 11,
    streamer_id: 3,
    streamer_name: 'retro_gamer',
    title: 'Story Mode Playthrough - Epic Adventure',
    category_name: 'Story Games',
    duration: 10200, // 170 minutes
    file_size: 1024 * 1024 * 1700, // 1.7 GB
    recorded_at: '2025-11-10T17:30:00Z',
    thumbnail_url: null,
    file_path: '/recordings/retro_gamer/Season 2025-11/retro_gamer - S202511E05 - Story_Mode_Playthrough.ts',
    viewer_count: 1500,
    has_chapters: true
  },
  {
    id: 12,
    streamer_id: 1,
    streamer_name: 'streamer_alpha',
    title: 'Q&A Stream - Answering Your Questions',
    category_name: 'Just Chatting',
    duration: 3600, // 60 minutes
    file_size: 1024 * 1024 * 600, // 600 MB
    recorded_at: '2025-11-09T15:00:00Z',
    thumbnail_url: null,
    file_path: '/recordings/streamer_alpha/Season 2025-11/streamer_alpha - S202511E99 - QA_Stream.ts',
    viewer_count: 890,
    has_chapters: false
  }
]

export const mockActiveRecordings = [
  {
    id: 101,
    streamer_id: 1,
    streamer_name: 'streamer_alpha',
    started_at: '2025-11-20T10:14:43Z',
    duration: 2340, // 39 minutes
    status: 'recording',
    output_file: '/recordings/maxim/Season 2025-11/maxim - S202511E02 - Pen_and_Paper_Preshow_!emma_!Holzkern_#Werbung.ts'
  }
]

export const mockCategories = [
  {
    id: '509658',
    name: 'Just Chatting',
    box_art_url: 'https://static-cdn.jtvnw.net/ttv-boxart/509658-{width}x{height}.jpg',
    streams: 0,
    is_favorite: true
  },
  {
    id: '2083908726',
    name: 'Backpack Battles',
    box_art_url: 'https://static-cdn.jtvnw.net/ttv-boxart/2083908726-{width}x{height}.jpg',
    streams: 0,
    is_favorite: true
  }
]

export const mockChapters = [
  {
    id: 1,
    stream_id: 1,
    start_time: 0,
    end_time: 600,
    title: 'Stream Start',
    category_id: '509658',
    category_name: 'Just Chatting'
  },
  {
    id: 2,
    stream_id: 1,
    start_time: 600,
    end_time: 1200,
    title: 'Main Content',
    category_id: '509658',
    category_name: 'Just Chatting'
  }
]

export const mockQueueStats = {
  total_tasks: 15,
  completed_tasks: 12,
  failed_tasks: 1,
  retried_tasks: 0,
  pending_tasks: 1,
  active_tasks: 1,
  workers: 4,
  is_running: true
}

export const mockActiveTasks = [
  {
    id: 'task_123',
    task_type: 'recording_stream',
    status: 'running',
    progress: 0,
    created_at: '2025-11-20T10:14:43Z',
    payload: {
      streamer_name: 'maxim',
      stream_id: 1
    }
  }
]

export const mockSettings = {
  recording: {
    enabled: true,
    default_quality: 'best',
    filename_template: 'Plex',
    max_parallel_recordings: 3
  },
  twitch: {
    oauth_token_expires: '2025-12-20T10:00:00Z',
    oauth_token_status: 'valid'
  },
  notifications: {
    enabled: true,
    stream_online: true,
    stream_offline: true,
    recording_started: true,
    recording_stopped: true
  }
}

export const mockProxies = [
  {
    id: 1,
    url: 'http://proxy1.example.com:8080',
    username: null,
    enabled: true,
    health_status: 'healthy',
    last_check: '2025-11-20T10:00:00Z',
    response_time_ms: 45,
    consecutive_failures: 0
  },
  {
    id: 2,
    url: 'http://proxy2.example.com:8080',
    username: 'user',
    enabled: true,
    health_status: 'degraded',
    last_check: '2025-11-20T09:55:00Z',
    response_time_ms: 250,
    consecutive_failures: 1
  },
  {
    id: 3,
    url: 'http://proxy3.example.com:8080',
    username: null,
    enabled: false,
    health_status: 'failed',
    last_check: '2025-11-20T09:50:00Z',
    response_time_ms: null,
    consecutive_failures: 3
  }
]

export const mockVersionInfo = {
  version: '1.2.3',
  build_date: '2025-11-15',
  python_version: '3.12.0',
  streamlink_version: '8.0.0'
}

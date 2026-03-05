STREAM_CHUNK_SIZE = 64 * 1024

JELLYFIN_TICKS_PER_SECOND = 10_000_000

BROWSER_AUDIO_DEVICE_PROFILE: dict[str, object] = {
	"MaxStreamingBitrate": 8000000,
	"MaxStaticBitrate": 8000000,
	"MusicStreamingTranscodingBitrate": 128000,
	"MaxStaticMusicBitrate": 8000000,
	"DirectPlayProfiles": [
		{"Container": "opus", "Type": "Audio"},
		{"Container": "webm", "AudioCodec": "opus", "Type": "Audio"},
		{"Container": "mp3", "Type": "Audio"},
		{"Container": "aac", "Type": "Audio"},
		{"Container": "m4a", "AudioCodec": "aac", "Type": "Audio"},
		{"Container": "m4b", "AudioCodec": "aac", "Type": "Audio"},
		{"Container": "flac", "Type": "Audio"},
		{"Container": "wav", "Type": "Audio"},
		{"Container": "ts", "AudioCodec": "mp3", "Type": "Audio"},
	],
	"TranscodingProfiles": [
		{
			"Container": "opus",
			"Type": "Audio",
			"AudioCodec": "opus",
			"Context": "Streaming",
			"Protocol": "http",
			"MaxAudioChannels": "2",
		}
	],
}

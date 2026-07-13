VIDEO_QUALITY_CHOICES = [
    ("best", "Best available"),
    ("1080p", "1080p"),
    ("720p", "720p"),
    ("480p", "480p"),
    ("360p", "360p"),
    ("smallest", "Lowest size"),
]

AUDIO_FORMAT_CHOICES = [
    ("mp3", "MP3"),
    ("m4a", "M4A"),
    ("aac", "AAC"),
    ("best", "Best available audio"),
]

VIDEO_FORMAT_SELECTORS = {
    "best": "bestvideo*+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "smallest": "worstvideo+worstaudio/worst",
}


def video_selector(quality):
    return VIDEO_FORMAT_SELECTORS.get(quality or "best", VIDEO_FORMAT_SELECTORS["best"])


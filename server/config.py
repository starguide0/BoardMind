"""Server configuration constants."""

OLLAMA_HOST = "http://localhost:11434"
TEXT_MODEL = "llama3:latest"
VISION_MODEL = "llava:latest"

# WebSocket
WS_PING_INTERVAL = 30  # seconds
WS_PING_TIMEOUT = 10   # seconds

# Game session
SESSION_IDLE_TIMEOUT = 600  # 10 minutes
TURN_TIMER_DEFAULT = 120    # 2 minutes per turn
TURN_TIMER_WARNING = 30     # warning at 30 seconds remaining

# Vision
FRAME_MIN_INTERVAL = 0.5  # minimum seconds between frame analyses

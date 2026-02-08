"""Board Game AI Server - WebSocket based."""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from services.llm_service import LLMService
from services.vision_service import VisionService
from services.session_manager import SessionManager
from services.game_manager import GameManager
from handlers.websocket_handler import WebSocketHandler

app = FastAPI(title="Board Game AI Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
llm_service = LLMService()
vision_service = VisionService(llm_service)
session_manager = SessionManager()
game_manager = GameManager(llm_service, vision_service)
ws_handler = WebSocketHandler(session_manager, game_manager)


@app.get("/")
def read_root():
    return {"message": "Board Game AI Server is running"}


@app.get("/api/health")
async def health_check():
    try:
        response = await llm_service.chat("Hi", system_prompt="Reply with 'OK'")
        return {"status": "online", "llm_response": response}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@app.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket):
    await ws_handler.handle_connection(websocket)

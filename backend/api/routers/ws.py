from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel


class BroadcastRequest(BaseModel):
    text: str
    room: str = "default"


class ConnectionManager:
    def __init__(self) -> None:
        self.connected: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, room_name: str):
        await websocket.accept()
        self.connected[room_name].add(websocket)

    async def disconnect(self, websocket: WebSocket, room_name: str):
        room_connections = self.connected.get(room_name)
        if room_connections is None:
            return
        room_connections.discard(websocket)
        if not room_connections:
            self.connected.pop(room_name, None)

    async def broadcast(self, message: str, room_name: str):
        disconnected: list[WebSocket] = []
        for websocket in list(self.connected.get(room_name, set())):
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            await self.disconnect(websocket, room_name)

    async def broadcast_all(self, message: str):
        for room_name in list(self.connected.keys()):
            await self.broadcast(message, room_name)


manager = ConnectionManager()
router = APIRouter(prefix="")


async def _handle_room_socket(websocket: WebSocket, room_name: str):
    await manager.connect(websocket, room_name)
    try:
        while True:
            message = await websocket.receive_text()
            await manager.broadcast(message, room_name)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, room_name)
    except Exception:
        await manager.disconnect(websocket, room_name)


@router.websocket("/ws/subtitles")
async def subtitles_default_room(websocket: WebSocket):
    room_name = websocket.query_params.get("room", "default")
    await _handle_room_socket(websocket, room_name)


@router.websocket("/ws/subtitles/{room_name}")
async def subtitles_named_room(websocket: WebSocket, room_name: str):
    await _handle_room_socket(websocket, room_name)


@router.post("/ws/broadcast")
async def broadcast_message(body: BroadcastRequest) -> dict:
    await manager.broadcast(body.text, body.room)
    return {"ok": True}

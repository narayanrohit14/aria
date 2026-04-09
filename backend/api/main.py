import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


def configure_logging() -> logging.Logger:
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    return logging.getLogger("aria-api")


logger = configure_logging()
connected_clients: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting aria-api")
    print("ARIA API startup")
    try:
        yield
    finally:
        logger.info("Shutting down aria-api")
        print("ARIA API shutdown")


app = FastAPI(title="ARIA API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aria-api", "version": "0.1.0"}


@app.get("/api/v1/status")
async def status() -> dict[str, str]:
    return {"environment": os.getenv("ARIA_ENV", "development")}


@app.websocket("/ws/subtitles")
async def subtitles_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info("WebSocket client connected. Total clients: %s", len(connected_clients))

    try:
        while True:
            message = await websocket.receive_text()
            disconnected_clients: list[WebSocket] = []

            for client in connected_clients:
                if client is websocket:
                    continue
                try:
                    await client.send_text(message)
                except RuntimeError:
                    disconnected_clients.append(client)
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed to broadcast message: %s", exc)
                    disconnected_clients.append(client)

            for client in disconnected_clients:
                connected_clients.discard(client)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:  # pragma: no cover
        logger.warning("WebSocket connection error: %s", exc)
    finally:
        connected_clients.discard(websocket)
        logger.info("WebSocket client removed. Total clients: %s", len(connected_clients))

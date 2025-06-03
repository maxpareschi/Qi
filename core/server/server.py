# server.py
"""
Main FastAPI application for the Qi Core Server.

This module sets up the FastAPI instance, defines the root HTTP endpoint,
and the primary WebSocket endpoint (`/ws`) for Qi communications.
It also configures middleware based on the development mode (dev proxy or SPA static files).
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from core.bases.models import QiMessage, QiSession
from core.config import qi_config
from core.logger import get_logger
from core.network.hub import hub
from core.server.middleware import (
    QiDevProxyMiddleware,
    QiSPAStaticFilesMiddleware,
)

log = get_logger(__name__)


qi_server = FastAPI(
    title="Qi Core Server",
    version="1.0.0",
    description="WebSocket-based communication server for Qi framework.",
)
"""The main FastAPI application instance for the Qi server."""


@qi_server.get("/")
async def root():
    """Simple HTTP GET endpoint for the root path to confirm the server is running."""
    return {"message": "Qi - Fastapi local server is running!"}


@qi_server.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """
    Main WebSocket endpoint for Qi communications.

    Handles the lifecycle of a WebSocket connection:
    1. Accepts the connection.
    2. Receives initial session data, validates it, and registers the session with the Qi Hub.
       If session data is invalid or registration fails, the connection is closed.
    3. Enters a loop to receive JSON messages from the client.
       - Validates each message against the QiMessage model.
       - Publishes valid messages to the Qi Hub for processing.
       - Logs errors for invalid messages but continues processing.
    4. Handles WebSocket disconnection or other errors by unregistering the session from the Hub.

    Args:
        ws: The FastAPI WebSocket object representing the client connection.
    """
    await ws.accept()
    session: QiSession | None = None  # Initialize session to None

    try:
        init_data = await ws.receive_json()
        # Attempt to validate the session data first
        try:
            session = QiSession.model_validate(init_data)
        except ValidationError as e:
            log.warning(f"Invalid session initialization data: {e}. Raw: {init_data}")
            await ws.close(
                code=4401
            )  # 4401: Custom code for Unauthorized/Invalid Session
            return

        # If session is validated, proceed to register
        await hub.register(ws, session)
        log.info(
            f"WebSocket session registered: {session.logical_id} (id: {session.id})"
        )

    except WebSocketDisconnect:
        # This can happen if client disconnects during or immediately after sending init_data
        # but before hub.register completes or if it sends non-JSON init_data.
        log.warning("WebSocket disconnected during session initialization.")
        # No session to unregister if `session` is still None or hub.register failed
        # If ws.close was already called (e.g. for ValidationError), this might error, but FastAPI handles it.
        await ws.close(code=4000)  # Generic abnormal closure
        return
    except Exception as e:
        # Catch any other unexpected errors during session initialization/registration
        log.error(f"Session registration failed: {e}")
        # Ensure session object is available for unregister if it was created
        if session:
            await hub.unregister(session.id)
        await ws.close(
            code=4500
        )  # 4500: Custom code for Internal Server Error / Registration Failed
        return

    # If session registration was successful, session object is guaranteed to be set.
    try:
        async for raw_json_message in ws.iter_json():
            try:
                message = QiMessage.model_validate(raw_json_message)
                await hub.publish(message)
            except ValidationError as e:
                log.warning(
                    f"Invalid message from session {session.id if session else 'Unknown'}: {e}. Raw: {raw_json_message}"
                )
                # Potentially send an error reply to the client if the protocol supports it
                # For now, just log and continue processing other messages.
            except Exception as e:
                # Catch errors during message model validation or hub.publish
                log.error(
                    f"Error processing message from session {session.id if session else 'Unknown'}: {e}"
                )
    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected: session={session.id if session else 'N/A'}")
    except Exception as e:
        # Catch any other unexpected errors during the message receiving loop
        log.error(
            f"WebSocket error for session {session.id if session else 'N/A'}: {e}"
        )
    finally:
        if session:  # Ensure session was successfully initialized before unregistering
            log.info(
                f"Unregistering WebSocket session: {session.logical_id} (id: {session.id})"
            )
            await hub.unregister(session.id)
        else:
            log.info(
                "WebSocket connection closed without successful session registration."
            )
        # FastAPI's WebSocket implementation handles the actual socket closure state internally.
        # We ensure our application-level cleanup (unregister) happens.


if qi_config.dev_mode:
    qi_server.add_middleware(QiDevProxyMiddleware)
    log.debug("Dev mode enabled: using QiDevProxyMiddleware for routing.")
else:
    qi_server.add_middleware(QiSPAStaticFilesMiddleware)
    log.debug("Production mode (or dev_mode=False): using QiSPAStaticFilesMiddleware.")

# Optional: Add a docstring for QiDevProxyMiddleware and QiSPAStaticFilesMiddleware
# in core/server/middleware.py if not already present.

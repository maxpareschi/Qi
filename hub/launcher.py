import asyncio
import os
import threading
from pathlib import Path

from core.addon.manager import QiAddonManager
from core.constants import BASE_PATH
from core.db.bus_handlers import register_db_handlers
from core.db.file_db import JsonFileDbAdapter
from core.db.manager import QiDbManager
from core.db.mock_auth import MockAuthAdapter
from core.gui.window_manager import QiWindowManager
from core.launch_config import qi_launch_config
from core.logger import get_logger
from core.settings.bus_handlers import register_settings_handlers
from core.settings.manager import QiSettingsManager
from hub.lib.runners import run_server

log = get_logger(__name__)


def initialize_db_manager(db_manager: QiDbManager):
    """
    Initialize the database manager with mock adapters.
    """
    # Create a data directory in the project root
    data_dir = Path(BASE_PATH) / "data"
    data_dir.mkdir(exist_ok=True)

    # Initialize adapters
    auth_adapter = MockAuthAdapter()
    file_adapter = JsonFileDbAdapter(str(data_dir))

    # Set adapters on the manager
    db_manager.set_auth_adapter(auth_adapter)
    db_manager.set_file_adapter(file_adapter)

    # Register message bus handlers
    register_db_handlers(db_manager)

    log.info("Database manager initialized with mock adapters")


def initialize_addon_manager():
    """
    Initialize the addon manager and load addons.
    """
    addon_manager = QiAddonManager(qi_launch_config.addon_paths)
    addon_manager.discover_addons()

    # Phase 1: Load provider addons (auth, db)
    try:
        addon_manager.load_provider_addons()
        log.info("Provider addons loaded successfully")
    except Exception as e:
        log.error(f"Failed to load provider addons: {e}")
        raise

    # TODO: Authentication handshake would happen here

    # Phase 2: Load regular addons
    try:
        addon_manager.load_regular_addons()
        log.info("Regular addons loaded successfully")
    except Exception as e:
        log.error(f"Failed to load regular addons: {e}")
        raise

    return addon_manager


async def initialize_settings_manager(addon_manager: QiAddonManager):
    """
    Initialize the settings manager and build the effective settings.
    """
    settings_manager = QiSettingsManager(addon_manager)
    await settings_manager.build_settings()

    # Register message bus handlers
    register_settings_handlers(settings_manager)

    log.info("Settings manager initialized")
    return settings_manager


def bind_window_manager(window_manager):
    """
    Register window manager message bus handlers.
    """
    # TODO: Implement window manager message handlers
    pass


def qi_gui_launcher():
    """
    Launcher for the hub.
    """
    # Create an asyncio event loop to run async functions
    loop = asyncio.get_event_loop()

    # Initialize the database manager
    db_manager = QiDbManager()
    initialize_db_manager(db_manager)

    # Initialize the addon manager
    try:
        addon_manager = initialize_addon_manager()
    except Exception as e:
        log.critical(f"Failed to initialize addon manager: {e}")
        return

    # Initialize the settings manager
    try:
        settings_manager = loop.run_until_complete(
            initialize_settings_manager(addon_manager)
        )
    except Exception as e:
        log.critical(f"Failed to initialize settings manager: {e}")
        return

    # Initialize the window manager
    window_manager = QiWindowManager()
    bind_window_manager(window_manager)

    # Start the server
    server_thread: threading.Thread = run_server(
        qi_launch_config.host,
        qi_launch_config.port,
        qi_launch_config.ssl_key_path,
        qi_launch_config.ssl_cert_path,
        qi_launch_config.dev_mode,
    )

    icon_path = os.path.join(
        BASE_PATH,
        "resources",
        "qi-icons",
        "qi_512.png",
    ).replace("\\", "/")

    window_manager.create_window(addon="addon-skeleton", session_id="main-session")
    window_manager.run(
        icon=icon_path,
    )

    # Clean shutdown
    addon_manager.close_all()
    log.info("All addons closed")

    os._exit(0)

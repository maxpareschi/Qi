# Qi Framework - New Architecture

This document provides an overview of the new architecture for the Qi Framework.

## Overview

The Qi Framework is a modular application framework designed for building desktop applications with web technologies. It provides a robust foundation for building applications with a plugin-based architecture.

The new architecture is designed to be:

- **Modular**: Components are self-contained and can be easily replaced or extended.
- **Event-driven**: Components communicate through events, reducing coupling.
- **Dependency-injected**: Components declare their dependencies explicitly, making the system more testable.
- **Asynchronous**: The system is built around asyncio for high performance and responsiveness.

## Core Components

### Dependency Injection Container

The heart of the new architecture is a simple dependency injection container that allows components to declare their dependencies explicitly. This makes the system more testable and the dependencies more visible.

```python
from core_new.di import container

# Register a singleton service
container.register_singleton("service_name", lambda: ServiceClass())

# Get a service
service = container.get("service_name")
```

### Message Bus

The message bus provides a publish-subscribe and request-reply messaging system. It allows components to register handlers for specific topics and to send messages to those topics.

```python
from core_new.messaging.bus import Message, MessageType, Session
from core_new.messaging.hub import hub

# Register a handler for a topic
@hub.on("topic.name")
async def handle_topic(message: Message):
    # Handle the message
    return {"result": "success"}

# Send a request and wait for a reply
result = await hub.request("topic.name", {"param": "value"})
```

### Addon System

The addon system allows extending the application with plugins. Addons can provide new functionality, UI components, or services.

```python
from core_new.addon.base import AddonBase

class MyAddon(AddonBase):
    @property
    def name(self) -> str:
        return "my_addon"

    def register(self) -> None:
        # Register services, routes, etc.
        pass
```

### Settings System

The settings system provides a way to store and retrieve application settings. It supports different scopes (global, bundle, project, user) and validation.

```python
from core_new.di import container

# Get the settings manager
settings_manager = container.get("settings_manager")

# Get a setting value
value = await settings_manager.get_value("group.key")

# Update a setting value
await settings_manager.patch_value("group.key", "new_value")
```

### Bundle System

The bundle system allows defining different configurations of the application. A bundle defines which addons are loaded and provides environment variables.

```python
from core_new.di import container

# Get the bundle manager
bundle_manager = container.get("bundle_manager")

# Get the active bundle
active_bundle = bundle_manager.get_active_bundle()

# Set the active bundle
await bundle_manager.set_active_bundle("bundle_name")
```

### Server

The server provides a FastAPI server with WebSocket support for communication with clients.

```python
from core_new.di import container

# Get the server
server = container.get("server")

# Add a router
server.add_router(my_router)

# Start the server
await server.start()
```

### Window Manager

The window manager provides a way to open and manage GUI windows.

```python
from core_new.di import container

# Get the window manager
window_manager = container.get("window_manager")

# Open a window
window_id = await window_manager.open_window(
    url="http://localhost:8000/ui/",
    title="My Window",
    width=800,
    height=600,
)

# Close a window
await window_manager.close_window(window_id)
```

## Application Structure

The application is structured as follows:

- `core_new/`: Core components of the framework.
  - `addon/`: Addon system.
  - `bundle/`: Bundle system.
  - `db/`: Database system.
  - `gui/`: GUI components.
  - `messaging/`: Message bus and hub.
  - `server/`: Server components.
  - `settings/`: Settings system.
  - `config.py`: Configuration system.
  - `di.py`: Dependency injection container.
  - `logger.py`: Logging system.
  - `models.py`: Data models.
- `app_new/`: Application-specific code.
  - `application.py`: Main application class.
  - `main.py`: Entry point.

## Starting the Application

To start the application, run:

```bash
python app_new/main.py
```

This will:

1. Initialize the application.
2. Load bundles and addons.
3. Start the server.
4. Open the main window (if not in headless mode).

## Extending the Application

To extend the application, you can:

- Create new addons in the `addons/` directory.
- Create new bundles in the `config/bundles.toml` file.
- Create new settings in addon's `get_settings()` method.
- Create new API routes in addon's `register()` method.

## Conclusion

The new architecture provides a solid foundation for building modular, extensible applications. It is designed to be easy to understand, maintain, and extend. 
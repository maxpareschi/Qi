import { browser } from "$app/environment";
import { windowState } from "$lib/states/qi.windowState.svelte";

/**
 * Helper to get a context field from multiple sources in priority order
 */
function getContextField(field, urlParams, stored, global, path) {
  return (
    urlParams.get(field) ||
    stored[field] ||
    global[field] ||
    path[field] ||
    null
  );
}

/**
 * Detect business context from various sources in priority order:
 * 1. URL parameters (highest priority)
 * 2. sessionStorage (persistent)
 * 3. Global variables (set by server/addon)
 * 4. Path-based detection (fallback)
 */
function detectContext() {
  if (!browser) {
    return { project: null, entity: null, task: null };
  }

  const urlParams = new URLSearchParams(location.search);
  const stored = JSON.parse(sessionStorage.getItem("qiContext") || "{}");
  const global = window.qi_context || {};
  const path = {}; // Placeholder for future path-based detection

  const context = {
    project: getContextField("project", urlParams, stored, global, path),
    entity: getContextField("entity", urlParams, stored, global, path),
    task: getContextField("task", urlParams, stored, global, path),
  };

  // Store detected context for persistence (only if we found something)
  if (context.project || context.entity || context.task) {
    sessionStorage.setItem("qiContext", JSON.stringify(context));

    if (import.meta.env?.DEV) {
      console.log("Context detected:", context);
    }
  }

  return context;
}

/**
 * Detect context with window-specific storage
 */
function detectContextForWindow(window_id) {
  if (!browser) {
    return { project: null, entity: null, task: null };
  }

  const urlParams = new URLSearchParams(location.search);
  const windowStorageKey = `qiContext_${window_id}`;
  const stored = JSON.parse(sessionStorage.getItem(windowStorageKey) || "{}");
  const global = window.qi_context || {};
  const path = {}; // Placeholder for future path-based detection

  const context = {
    project: getContextField("project", urlParams, stored, global, path),
    entity: getContextField("entity", urlParams, stored, global, path),
    task: getContextField("task", urlParams, stored, global, path),
  };

  // Store detected context with window-specific key
  if (context.project || context.entity || context.task) {
    sessionStorage.setItem(windowStorageKey, JSON.stringify(context));

    if (import.meta.env?.DEV) {
      console.log(
        "Window-specific context detected:",
        context,
        "for window:",
        window_id
      );
    }
  }

  return context;
}

// ============================================================================
// REACTIVE STATE & FUNCTIONS
// ============================================================================

export const qiConnection = $state({
  // Reactive properties
  session_id: null,
  addon: null,
  window_id: null,
  socket: null,
  context: null,
  user: null,
  connected: false,

  /**
   * Send a message through the WebSocket connection.
   * All parameters are optional with sensible defaults.
   *
   * @param {string} topic - Message topic (required)
   * @param {Object} options - Optional parameters
   * @param {Object} options.payload - Message payload data (default: {})
   * @param {Object} options.context - Context override (optional)
   * @param {Object} options.user - User override (optional)
   * @param {string} options.reply_to - ID of message this is replying to (optional)
   * @param {Object} options.source - Source override for power routing (optional, server constructs by default)
   *
   * @example
   * // Simple usage - just topic
   * qiConnection.emit("wm.window.close")
   *
   * // With payload
   * qiConnection.emit("my.topic", {payload: {data: "value"}})
   *
   * // Reply to a message
   * qiConnection.emit("response", {payload: {result: "ok"}, reply_to: originalMsg.message_id})
   *
   * // Power routing - override source for advanced scenarios
   * qiConnection.emit("cross.window.message", {
   *   payload: {data: "value"},
   *   source: {addon: "other-addon", session_id: "other-session", window_id: "target-window"}
   * })
   */
  emit(topic, options = {}) {
    if (!qiConnection.connected) {
      console.warn("Cannot send message: WebSocket not connected");
      return;
    }

    const {
      payload = {},
      context = null,
      user = null,
      reply_to = null,
      source = null,
    } = options;

    // Build context: use provided context or default context
    let finalContext;
    if (context) {
      finalContext = {
        project:
          context.project !== undefined
            ? context.project
            : qiConnection.context?.project || null,
        entity:
          context.entity !== undefined
            ? context.entity
            : qiConnection.context?.entity || null,
        task:
          context.task !== undefined
            ? context.task
            : qiConnection.context?.task || null,
      };
    } else {
      finalContext = {
        project: qiConnection.context?.project || null,
        entity: qiConnection.context?.entity || null,
        task: qiConnection.context?.task || null,
      };
    }

    // Build source information for routing
    // Server will construct authoritative source, but client can provide override for power routing
    let finalSource = null;
    if (source) {
      // Power routing scenario - client explicitly provides source override
      finalSource = {
        addon: source.addon || qiConnection.addon,
        session_id: source.session_id || qiConnection.session_id,
        window_id:
          source.window_id !== undefined
            ? source.window_id
            : qiConnection.window_id,
        user:
          source.user !== undefined
            ? source.user
            : user || qiConnection.user || null,
      };

      if (import.meta.env?.DEV) {
        console.log(
          "Power routing: Using custom source for",
          topic,
          finalSource
        );
      }
    } else {
      // Normal scenario - provide minimal source info, server will construct authoritative version
      finalSource = {
        addon: qiConnection.addon,
        session_id: qiConnection.session_id,
        window_id: qiConnection.window_id,
        user: user || qiConnection.user || null,
      };
    }

    // Build user information
    const finalUser = user || qiConnection.user || null;

    const envelope = {
      message_id: crypto.randomUUID(),
      topic,
      payload,
      context: finalContext,
      source: finalSource,
      user: finalUser,
      reply_to: reply_to,
      timestamp: Date.now() / 1000,
    };

    if (import.meta.env?.DEV) {
      console.log(`${topic} → server`);
    }

    try {
      qiConnection.socket.send(JSON.stringify(envelope));
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  },

  on(topic, handler) {
    console.warn(
      "qiConnection not initialized. Call initQiConnection() first."
    );
    return () => {};
  },

  off(topic, handler) {
    console.warn(
      "qiConnection not initialized. Call initQiConnection() first."
    );
  },

  isConnected() {
    return this.connected;
  },

  getConnectionInfo() {
    return {
      session_id: this.session_id,
      addon: this.addon,
      context: this.context,
      user: this.user,
      window_id: this.window_id,
      connected: this.connected,
    };
  },

  updateContext(newContext) {
    this.context = { ...this.context, ...newContext };
    if (browser && this.window_id) {
      const windowStorageKey = `qiContext_${this.window_id}`;
      sessionStorage.setItem(windowStorageKey, JSON.stringify(this.context));
    }
  },

  updateUser(newUser) {
    this.user = { ...this.user, ...newUser };
  },
});

// Internal message handlers
const _messageHandlers = new Map();

// ============================================================================
// INITIALIZATION
// ============================================================================

export const initQiConnection = async () => {
  if (!browser) {
    console.warn("initQiConnection called outside browser environment");
    return;
  }

  // Initialize session_id (this can be shared across windows)
  let session_id = sessionStorage.getItem("qiSessionId");
  if (!session_id) {
    const params = new URLSearchParams(location.search);
    session_id = params.get("session_id") ?? crypto.randomUUID();
    sessionStorage.setItem("qiSessionId", session_id);
  }
  qiConnection.session_id = session_id;

  // Initialize addon (this can be shared across windows)
  let addon = sessionStorage.getItem("qiAddon");
  if (!addon) {
    addon = location.pathname.split("/").filter(Boolean)[0] ?? "";
    sessionStorage.setItem("qiAddon", addon);
  }
  qiConnection.addon = addon;

  // Initialize window_id with priority order:
  // 1. URL parameters (highest priority - from server)
  // 2. Generate fallback

  let window_id = null;
  const urlParams = new URLSearchParams(location.search);

  // First try URL parameters (from server)
  window_id = urlParams.get("window_id");
  if (window_id) {
    if (import.meta.env?.DEV) {
      console.log("Window ID from URL parameter:", window_id);
    }
  }

  // Ensure window_id is always null or a string, never an object
  if (window_id && typeof window_id === "string") {
    qiConnection.window_id = window_id;
    if (import.meta.env?.DEV) {
      console.log("Window ID set to:", window_id);
    }
  } else {
    // Fallback: generate a unique window ID if URL parameter isn't available
    // This ensures each window instance has a unique identifier
    // Note: Don't use sessionStorage as it's shared between windows
    const fallback_window_id = `window_${crypto.randomUUID()}`;
    qiConnection.window_id = fallback_window_id;

    if (import.meta.env?.DEV) {
      console.log("Generated fallback window ID:", fallback_window_id, {
        received: window_id,
        type: typeof window_id,
      });
    }
  }

  // Now initialize context with window-specific storage
  qiConnection.context = detectContextForWindow(qiConnection.window_id);

  // Initialize user (for future auth integration)
  qiConnection.user = null; // TODO: Detect user from auth system

  // Initialize WebSocket - check if existing connection is still valid
  const existingWs = window.__qiConnection;
  const needsNewConnection =
    !existingWs ||
    existingWs.readyState === WebSocket.CLOSED ||
    existingWs.readyState === WebSocket.CLOSING;

  if (needsNewConnection) {
    if (import.meta.env?.DEV && existingWs) {
      console.log(
        "Previous WebSocket connection invalid, creating new one. State:",
        existingWs.readyState
      );
    }

    const ws = new WebSocket(
      `ws://127.0.0.1:8000/ws?session_id=${session_id}&window_id=${qiConnection.window_id}`
    );

    // Connection event handlers
    ws.addEventListener("open", () => {
      qiConnection.connected = true;

      if (import.meta.env?.DEV) {
        console.log(
          `WebSocket connected: session_id=${session_id}, window_id=${qiConnection.window_id?.slice(
            0,
            8
          )}...`
        );
      }
    });

    ws.addEventListener("close", () => {
      qiConnection.connected = false;
      if (import.meta.env?.DEV) {
        console.log("WebSocket disconnected");
      }
    });

    ws.addEventListener("error", (error) => {
      qiConnection.connected = false;
      if (import.meta.env?.DEV) {
        console.error("WebSocket error:", error);
      }
    });

    // Message handler
    ws.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle heartbeat messages (simple JSON, not envelopes)
        if (data.pong === true || data.ping === true) {
          if (import.meta.env?.DEV && data.ping === true) {
            console.log("Received ping from server");
          }
          return;
        }

        // Treat as envelope
        const envelope = data;

        // Server-side routing now handles window targeting
        // All messages received here are intended for this window
        if (import.meta.env?.DEV) {
          console.log(
            `${envelope.topic} → window ${qiConnection.window_id?.slice(
              0,
              8
            )}...`
          );
        }

        // Route to topic handlers
        const handlers = _messageHandlers.get(envelope.topic);
        if (handlers?.size > 0) {
          handlers.forEach((handler) => {
            try {
              handler(envelope);
            } catch (error) {
              console.error(
                `Error in handler for topic "${envelope.topic}":`,
                error
              );
            }
          });
        } else if (import.meta.env?.DEV) {
          console.warn(`No handlers registered for topic: "${envelope.topic}"`);
        }
      } catch (error) {
        console.error("Failed to parse incoming message:", error, event.data);
      }
    });

    window.__qiConnection = ws;
  }

  qiConnection.socket = window.__qiConnection;
  qiConnection.connected = qiConnection.socket?.readyState === WebSocket.OPEN;

  // Initialize function implementations
  qiConnection.emit = (topic, options = {}) => {
    if (!qiConnection.connected) {
      console.warn("Cannot send message: WebSocket not connected");
      return;
    }

    const {
      payload = {},
      context = null,
      user = null,
      reply_to = null,
      source = null,
    } = options;

    // Build context: use provided context or default context
    let finalContext;
    if (context) {
      finalContext = {
        project:
          context.project !== undefined
            ? context.project
            : qiConnection.context?.project || null,
        entity:
          context.entity !== undefined
            ? context.entity
            : qiConnection.context?.entity || null,
        task:
          context.task !== undefined
            ? context.task
            : qiConnection.context?.task || null,
      };
    } else {
      finalContext = {
        project: qiConnection.context?.project || null,
        entity: qiConnection.context?.entity || null,
        task: qiConnection.context?.task || null,
      };
    }

    // Build source information for routing
    // Server will construct authoritative source, but client can provide override for power routing
    let finalSource = null;
    if (source) {
      // Power routing scenario - client explicitly provides source override
      finalSource = {
        addon: source.addon || qiConnection.addon,
        session_id: source.session_id || qiConnection.session_id,
        window_id:
          source.window_id !== undefined
            ? source.window_id
            : qiConnection.window_id,
        user:
          source.user !== undefined
            ? source.user
            : user || qiConnection.user || null,
      };

      if (import.meta.env?.DEV) {
        console.log(
          "Power routing: Using custom source for",
          topic,
          finalSource
        );
      }
    } else {
      // Normal scenario - provide minimal source info, server will construct authoritative version
      finalSource = {
        addon: qiConnection.addon,
        session_id: qiConnection.session_id,
        window_id: qiConnection.window_id,
        user: user || qiConnection.user || null,
      };
    }

    // Build user information
    const finalUser = user || qiConnection.user || null;

    const envelope = {
      message_id: crypto.randomUUID(),
      topic,
      payload,
      context: finalContext,
      source: finalSource,
      user: finalUser,
      reply_to: reply_to,
      timestamp: Date.now() / 1000,
    };

    if (import.meta.env?.DEV) {
      console.log(`${topic} → server`);
    }

    try {
      qiConnection.socket.send(JSON.stringify(envelope));
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  };

  qiConnection.on = (topic, handler) => {
    if (!_messageHandlers.has(topic)) {
      _messageHandlers.set(topic, new Set());
    }
    _messageHandlers.get(topic).add(handler);

    if (import.meta.env?.DEV) {
      console.log(`Handler registered: ${topic}`);
    }

    return () => qiConnection.off(topic, handler);
  };

  qiConnection.off = (topic, handler) => {
    const handlers = _messageHandlers.get(topic);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        _messageHandlers.delete(topic);
      }

      if (import.meta.env?.DEV) {
        console.log(`Unregistered handler for topic: "${topic}"`);
      }
    }
  };

  // Set up window subscriptions
  const { setupWindowSubscriptions } = await import(
    "./qi.windowSubscriptions.svelte"
  );
  setupWindowSubscriptions();
};

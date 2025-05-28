import { browser } from "$app/environment";

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
 * Detect context from various sources in priority order:
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
      console.log("🎯 Context detected:", context);
    }
  }

  return context;
}

/**
 * Detect context with window-specific storage
 */
function detectContextForWindow(window_uuid) {
  if (!browser) {
    return { project: null, entity: null, task: null };
  }

  const urlParams = new URLSearchParams(location.search);
  const windowStorageKey = `qiContext_${window_uuid}`;
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
        "🎯 Window-specific context detected:",
        context,
        "for window:",
        window_uuid
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
  session: null,
  addon: null,
  socket: null,
  context: null,
  window_uuid: null,
  connected: false,

  // Functions (will be properly initialized in initQiConnection)
  /**
   * Send a message through the WebSocket connection.
   * @param {string} topic - Message topic
   * @param {Object} params - Named parameters
   * @param {Object} params.payload - Message payload data (default: {})
   * @param {Object} params.context - Business context override (project/entity/task) (optional)
   * @param {Object} params.source - Source context override (session/window_uuid/addon) (optional)
   * @param {Object} params.user - User context override (username/auth_data) (optional)
   * @param {string} params.reply_to - UUID of message this is replying to (optional)
   *
   * @example
   * // Basic usage
   * qiConnection.emit("my.topic", {payload: {data: "value"}})
   *
   * // Reply to a message
   * qiConnection.emit("response", {payload: {result: "ok"}, reply_to: originalMsg.message_id})
   *
   * // Override business context
   * qiConnection.emit("task.update", {payload: {status: "done"}, context: {project: "other-project"}})
   *
   * // Override user context
   * qiConnection.emit("user.action", {payload: {action: "save"}, user: {username: "admin"}})
   */
  emit(
    topic,
    {
      payload = {},
      context = null,
      source = null,
      user = null,
      reply_to = null,
    } = {}
  ) {
    console.warn(
      "qiConnection not initialized. Call initQiConnection() first."
    );
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
      session: this.session,
      addon: this.addon,
      context: this.context,
      window_uuid: this.window_uuid,
      connected: this.connected,
    };
  },

  updateContext(newContext) {
    this.context = { ...this.context, ...newContext };
    // Note: session is managed automatically and shouldn't be manually updated
    if (browser && this.window_uuid) {
      const windowStorageKey = `qiContext_${this.window_uuid}`;
      sessionStorage.setItem(windowStorageKey, JSON.stringify(this.context));
    }
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

  // Initialize session (this can be shared across windows)
  let session = sessionStorage.getItem("qiSession");
  if (!session) {
    const params = new URLSearchParams(location.search);
    session = params.get("session") ?? crypto.randomUUID();
    sessionStorage.setItem("qiSession", session);
  }
  qiConnection.session = session;

  // Initialize addon (this can be shared across windows)
  let addon = sessionStorage.getItem("qiAddon");
  if (!addon) {
    addon = location.pathname.split("/").filter(Boolean)[0] ?? "";
    sessionStorage.setItem("qiAddon", addon);
  }
  qiConnection.addon = addon;

  // Initialize context (will be set after window UUID is determined)
  qiConnection.context = null;

  // Initialize window UUID with priority order:
  // 1. URL parameters (highest priority - from server)
  // 2. pywebview API
  // 3. Generate fallback

  let window_uuid = null;
  const urlParams = new URLSearchParams(location.search);

  // First try URL parameters (from server)
  window_uuid = urlParams.get("window_uuid");
  if (window_uuid) {
    if (import.meta.env?.DEV) {
      console.log("🪟 Window UUID from URL parameter:", window_uuid);
    }
  } else {
    // Try pywebview API as fallback
    if (typeof window.pywebview !== "undefined" && window.pywebview.api) {
      try {
        const result = window.pywebview.api.get_window_uuid();
        // Handle both sync and async results
        if (result && typeof result.then === "function") {
          // It's a Promise, wait for it
          try {
            window_uuid = await result;
            if (import.meta.env?.DEV) {
              console.log(
                "🪟 Window UUID from pywebview API (async):",
                window_uuid
              );
            }
          } catch (e) {
            if (import.meta.env?.DEV) {
              console.log(
                "🪟 Failed to await window UUID from pywebview API",
                e
              );
            }
          }
        } else {
          // It's a direct value
          window_uuid = result;
          if (import.meta.env?.DEV) {
            console.log(
              "🪟 Window UUID from pywebview API (sync):",
              window_uuid
            );
          }
        }

        if (import.meta.env?.DEV) {
          console.log(
            "🪟 pywebview API available:",
            Object.keys(window.pywebview.api)
          );
        }
      } catch (e) {
        // pywebview API not available or method doesn't exist
        if (import.meta.env?.DEV) {
          console.log("🪟 Window UUID not available from pywebview API", e);
        }
      }
    } else {
      if (import.meta.env?.DEV) {
        console.log("🪟 pywebview not available", {
          pywebview_exists: typeof window.pywebview !== "undefined",
          api_exists: typeof window.pywebview?.api !== "undefined",
        });
      }
    }
  }

  // Ensure window_uuid is always null or a string, never an object
  if (window_uuid && typeof window_uuid === "string") {
    qiConnection.window_uuid = window_uuid;
    if (import.meta.env?.DEV) {
      console.log("🪟 Window UUID set to:", window_uuid);
    }
  } else {
    // Fallback: generate a unique window ID if pywebview API isn't available
    // This ensures each window instance has a unique identifier
    // Note: Don't use sessionStorage as it's shared between windows
    const fallback_window_id = `window_${crypto.randomUUID()}`;
    qiConnection.window_uuid = fallback_window_id;

    if (import.meta.env?.DEV) {
      console.log("🪟 Generated fallback window UUID:", fallback_window_id, {
        received: window_uuid,
        type: typeof window_uuid,
      });
    }
  }

  // Now initialize context with window-specific storage
  qiConnection.context = detectContextForWindow(qiConnection.window_uuid);

  // Initialize WebSocket - check if existing connection is still valid
  const existingWs = window.__qiConnection;
  const needsNewConnection =
    !existingWs ||
    existingWs.readyState === WebSocket.CLOSED ||
    existingWs.readyState === WebSocket.CLOSING;

  if (needsNewConnection) {
    if (import.meta.env?.DEV && existingWs) {
      console.log(
        "🔄 Previous WebSocket connection invalid, creating new one. State:",
        existingWs.readyState
      );
    }

    const ws = new WebSocket(
      `ws://127.0.0.1:8000/ws?session=${session}&window_uuid=${qiConnection.window_uuid}`
    );

    // Connection event handlers
    ws.addEventListener("open", () => {
      qiConnection.connected = true;

      if (import.meta.env?.DEV) {
        console.log(
          `🔗 WebSocket connected: session=${session}, window=${qiConnection.window_uuid?.slice(
            0,
            8
          )}...`
        );
      }
    });

    ws.addEventListener("close", () => {
      qiConnection.connected = false;
      if (import.meta.env?.DEV) {
        console.log("🔌 WebSocket disconnected");
      }
    });

    ws.addEventListener("error", (error) => {
      qiConnection.connected = false;
      if (import.meta.env?.DEV) {
        console.error("❌ WebSocket error:", error);
      }
    });

    // Message handler
    ws.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle heartbeat messages (simple JSON, not envelopes)
        if (data.pong === true || data.ping === true) {
          if (import.meta.env?.DEV && data.ping === true) {
            console.log("💓 Received ping from server");
          }
          return;
        }

        // Treat as envelope
        const envelope = data;

        // Server-side routing now handles window targeting
        // All messages received here are intended for this window
        if (import.meta.env?.DEV) {
          console.log(
            `📥 ${envelope.topic} → window ${qiConnection.window_uuid?.slice(
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
  qiConnection.emit = (
    topic,
    {
      payload = {},
      context = null,
      source = null,
      user = null,
      reply_to = null,
    } = {}
  ) => {
    if (!qiConnection.connected) {
      console.warn("Cannot send message: WebSocket not connected");
      return;
    }

    // Build business context (project/entity/task only)
    let finalContext = null;
    if (context || qiConnection.context) {
      finalContext = {
        project: context?.project ?? qiConnection.context?.project ?? null,
        entity: context?.entity ?? qiConnection.context?.entity ?? null,
        task: context?.task ?? qiConnection.context?.task ?? null,
      };
      // Remove null values for cleaner envelope
      finalContext = Object.fromEntries(
        Object.entries(finalContext).filter(([_, v]) => v !== null)
      );
      if (Object.keys(finalContext).length === 0) finalContext = null;
    }

    // Build source context (session/window_uuid/addon)
    let finalSource = {
      session: source?.session ?? qiConnection.session,
      window_uuid: source?.window_uuid ?? qiConnection.window_uuid ?? null,
      addon: source?.addon ?? qiConnection.addon ?? null,
    };
    // Remove null values for cleaner envelope
    finalSource = Object.fromEntries(
      Object.entries(finalSource).filter(([_, v]) => v !== null)
    );

    // Build user context (username/auth_data) - optional
    let finalUser = null;
    if (user) {
      finalUser = {
        username: user.username ?? "anonymous",
        auth_data: user.auth_data ?? {},
      };
    }

    // Extra safety check - ensure window_uuid is never an object
    if (
      finalSource.window_uuid &&
      typeof finalSource.window_uuid !== "string"
    ) {
      finalSource.window_uuid = null;
      if (import.meta.env?.DEV) {
        console.warn("🚨 window_uuid was not a string, setting to null");
      }
    }

    const envelope = {
      message_id: crypto.randomUUID(),
      topic,
      payload: payload || {},
      context: finalContext,
      source: finalSource,
      user: finalUser,
      reply_to: reply_to,
      timestamp: Date.now() / 1000,
    };

    if (import.meta.env?.DEV) {
      console.log(`📤 ${topic} → server`);
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
      console.log(`📝 Handler registered: ${topic}`);
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
        console.log(`📝 Unregistered handler for topic: "${topic}"`);
      }
    }
  };
};

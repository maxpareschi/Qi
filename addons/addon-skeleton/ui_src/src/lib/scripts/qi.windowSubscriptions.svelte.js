/**
 * Window State Synchronization Subscriptions
 *
 * This module handles all the window manager message subscriptions
 * that sync the local window state with the server-side window manager.
 */

import { qiConnection } from "./qi.windowConnections.svelte";

export function setupWindowSubscriptions() {
  // Set up window state synchronization handlers
  qiConnection.on("wm.window.maximized", (envelope) => {
    if (
      envelope.payload.window_id === qiConnection.window_id &&
      envelope.payload.success
    ) {
      // Import windowState dynamically to avoid circular imports
      import("$lib/states/qi.windowState.svelte").then(({ windowState }) => {
        windowState.isMaximized = envelope.payload.maximized;
        if (import.meta.env?.DEV) {
          console.log(
            "Window maximized state updated:",
            envelope.payload.maximized
          );
        }
      });
    }
  });

  qiConnection.on("wm.window.minimized", (envelope) => {
    if (
      envelope.payload.window_id === qiConnection.window_id &&
      envelope.payload.success
    ) {
      import("$lib/states/qi.windowState.svelte").then(({ windowState }) => {
        windowState.isMinimized = true;
        if (import.meta.env?.DEV) {
          console.log("Window minimized");
        }
      });
    }
  });

  qiConnection.on("wm.window.restored", (envelope) => {
    if (
      envelope.payload.window_id === qiConnection.window_id &&
      envelope.payload.success
    ) {
      import("$lib/states/qi.windowState.svelte").then(({ windowState }) => {
        windowState.isMaximized = false;
        windowState.isMinimized = false;
        if (import.meta.env?.DEV) {
          console.log("Window restored");
        }
      });
    }
  });

  qiConnection.on("wm.window.hidden", (envelope) => {
    if (
      envelope.payload.window_id === qiConnection.window_id &&
      envelope.payload.success
    ) {
      if (import.meta.env?.DEV) {
        console.log("Window hidden");
      }
    }
  });

  qiConnection.on("wm.window.shown", (envelope) => {
    if (
      envelope.payload.window_id === qiConnection.window_id &&
      envelope.payload.success
    ) {
      if (import.meta.env?.DEV) {
        console.log("Window shown");
      }
    }
  });

  qiConnection.on("wm.window.moved", (envelope) => {
    if (
      envelope.payload.window_id === qiConnection.window_id &&
      envelope.payload.success
    ) {
      if (import.meta.env?.DEV) {
        console.log("Window moved to:", envelope.payload.x, envelope.payload.y);
      }
    }
  });

  qiConnection.on("wm.window.resized", (envelope) => {
    if (
      envelope.payload.window_id === qiConnection.window_id &&
      envelope.payload.success
    ) {
      if (import.meta.env?.DEV) {
        console.log(
          "Window resized:",
          envelope.payload.width,
          "x",
          envelope.payload.height
        );
      }
    }
  });

  qiConnection.on("wm.window.closed", (envelope) => {
    if (envelope.payload.window_id === qiConnection.window_id) {
      if (import.meta.env?.DEV) {
        console.log("Window closed by server");
      }
      // The window will be closed by the server, no need to handle here
    }
  });
}

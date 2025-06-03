import { windowState } from "../states/qi.windowState.svelte";
import { qiConnection } from "./qi.windowConnections.svelte";

export const startResize = (event) => {
  windowState.isResizing = true;
  windowState.resizingSide = event.target.dataset.side;
  windowState.windowPosition = { x: window.screenX, y: window.screenY };
  windowState.windowSize = {
    width: window.innerWidth,
    height: window.innerHeight,
  };
  window.addEventListener("mousemove", resizeWindow);
  window.addEventListener("mouseup", stopResize);
};

export const stopResize = () => {
  windowState.isResizing = false;
  windowState.resizingSide = null;
  windowState.windowPosition = { x: 0, y: 0 };
  windowState.windowSize = { width: 0, height: 0 };
  window.removeEventListener("mousemove", resizeWindow);
  window.removeEventListener("mouseup", stopResize);
};

export const startMove = (event) => {
  windowState.isMoving = true;
  windowState.mousePosition = { x: event.clientX, y: event.clientY };
  window.addEventListener("mousemove", moveWindow);
  window.addEventListener("mouseup", stopMove);
};

export const stopMove = () => {
  windowState.isMoving = false;
  windowState.mousePosition = { x: 0, y: 0 };
  window.removeEventListener("mousemove", moveWindow);
  window.removeEventListener("mouseup", stopMove);
};

export const minimizeWindow = async () => {
  qiConnection.emit("wm.window.minimize");
  windowState.isMinimized = true;
};

export const maximizeWindow = async () => {
  qiConnection.emit("wm.window.maximize");
  windowState.isMaximized = true;
};

export const closeWindow = async () => {
  qiConnection.emit("wm.window.close");
};

export const restoreWindow = async () => {
  qiConnection.emit("wm.window.restore");
  windowState.isMaximized = false;
  windowState.isMinimized = false;
  windowState.isMoving = false;
  windowState.isResizing = false;
};

export const hideWindow = async () => {
  qiConnection.emit("wm.window.hide");
};

export const showWindow = async () => {
  qiConnection.emit("wm.window.show");
};

export const moveWindow = (event) => {
  let x = Math.ceil(event.screenX - windowState.mousePosition.x);
  let y = Math.ceil(event.screenY - windowState.mousePosition.y);

  qiConnection.emit("wm.window.move", {
    payload: {
      x: x,
      y: y,
    },
  });
};

export const resizeWindow = (event) => {
  let width = windowState.windowSize.width;
  let height = windowState.windowSize.height;

  switch (windowState.resizingSide) {
    case "left":
      width =
        windowState.windowPosition.x +
        windowState.windowSize.width -
        event.screenX;
      break;
    case "right":
      width = event.screenX - windowState.windowPosition.x;
      break;
    case "top":
      height =
        windowState.windowPosition.y +
        windowState.windowSize.height -
        event.screenY;
      break;
    case "bottom":
      height = event.screenY - windowState.windowPosition.y;
      break;
    case "bottom-right":
      width = event.screenX - windowState.windowPosition.x;
      height = event.screenY - windowState.windowPosition.y;
      break;
    case "bottom-left":
      width =
        windowState.windowPosition.x +
        windowState.windowSize.width -
        event.screenX;
      height = event.screenY - windowState.windowPosition.y;
      break;
  }

  width = Math.ceil(
    Math.max(width, windowState.minSize.width) * windowState.dpi
  );
  height = Math.ceil(
    Math.max(height, windowState.minSize.height) * windowState.dpi
  );

  qiConnection.emit("wm.window.resize", {
    payload: {
      width: width,
      height: height,
      edge: windowState.resizingSide,
    },
  });
};

export const getWindowState = async () => {
  return new Promise((resolve) => {
    const unsubscribe = qiConnection.on(
      "wm.window.state_response",
      (envelope) => {
        if (envelope.source.window_id === qiConnection.window_id) {
          unsubscribe();
          resolve(envelope.payload);
        }
      }
    );

    qiConnection.emit("wm.window.get_state");
  });
};

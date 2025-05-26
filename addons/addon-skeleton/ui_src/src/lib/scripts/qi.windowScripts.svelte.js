import { windowState } from "../states/qi.windowState.svelte";

export const minimizeWindow = () => {
  if (typeof pywebview !== "undefined") {
    pywebview.api.minimize();
  }
};

export const maximizeWindow = () => {
  if (typeof pywebview !== "undefined") {
    if (windowState.isMaximized) {
      pywebview.api.restore();
      windowState.isMaximized = false;
    } else {
      pywebview.api.maximize();
      windowState.isMaximized = true;
    }
  }
};

export const closeWindow = () => {
  if (typeof pywebview !== "undefined") {
    pywebview.api.close();
  }
};

export const startMove = (event) => {
  if (windowState.isMoving) return;
  windowState.mousePosition = { x: event.clientX, y: event.clientY };
  windowState.isMoving = true;
  window.addEventListener("mousemove", doMove);
  window.addEventListener("mouseup", stopMove);
};

export const stopMove = () => {
  if (!windowState.isMoving) return;
  windowState.isMoving = false;
  windowState.mousePosition = { x: 0, y: 0 };
  window.removeEventListener("mousemove", doMove);
  window.removeEventListener("mouseup", stopMove);
};

export const doMove = (event) => {
  if (!windowState.isMoving) return;
  let x = Math.ceil(event.screenX - windowState.mousePosition.x);
  let y = Math.ceil(event.screenY - windowState.mousePosition.y);
  pywebview.api.move(x, y);
};

export const startResize = (event) => {
  windowState.isResizing = true;
  windowState.resizingSide = event.target.dataset.side;
  windowState.windowPosition = { x: window.screenX, y: window.screenY };
  windowState.windowSize = {
    width: window.innerWidth,
    height: window.innerHeight,
  };
  window.addEventListener("mousemove", doResize);
  window.addEventListener("mouseup", stopResize);
};

export const stopResize = () => {
  windowState.isResizing = false;
  windowState.resizingSide = null;
  windowState.windowSize = { width: 0, height: 0 };
  windowState.windowPosition = { x: 0, y: 0 };
  window.removeEventListener("mousemove", doResize);
  window.removeEventListener("mouseup", stopResize);
};

export const doResize = (event) => {
  if (!windowState.isResizing) return;
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
  pywebview.api.resize(width, height, windowState.resizingSide);
};

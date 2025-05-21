<script>
  let { edges = ["left", "right", "bottom", "top", "handle"]} = $props();

  let isResizing = false;
  let windowPosition = { x: 0, y: 0 };
  let windowSize = { width: 0, height: 0 };
  let mousePosition = { x: 0, y: 0 };
  let edge = null;
  let minSize = { width: 400, height: 300 };

  function startResize(event) {
    if (isResizing) return;
    windowPosition = { x: window.screenX, y: window.screenY };
    windowSize = { width: window.innerWidth, height: window.innerHeight };
    isResizing = true;
    edge = event.target.dataset.edge;
    window.addEventListener("mousemove", doResize);
    window.addEventListener("mouseup", stopResize);
  }

  function stopResize() {
    if (!isResizing) return;
    isResizing = false;
    edge = null;
    mousePosition = { x: 0, y: 0 };
    windowPosition = { x: 0, y: 0 };
    windowSize = { width: 0, height: 0 };
    window.removeEventListener("mousemove", doResize);
    window.removeEventListener("mouseup", stopResize);
  }

  function doResize(event) {
    if (!isResizing) return;
    let width = windowSize.width;
    let height = windowSize.height;

    switch (edge) {
      case "left":
        width = windowPosition.x + windowSize.width - event.screenX;
        break;
      case "right":
        width = event.screenX - windowPosition.x;
        break;
      case "top":
        height = windowPosition.y + windowSize.height - event.screenY;
        break;
      case "bottom":
        height = event.screenY - windowPosition.y;
        break;
      case "handle":
        width = event.screenX - windowPosition.x;
        height = event.screenY - windowPosition.y;
    }

    width = Math.max(width, minSize.width);
    height = Math.max(height, minSize.height);
    pywebview.api.resize(width, height, edge);
  }
</script>

{#snippet resizeArea(edge)}
  <div
    class="window-resizer-{edge}"
    data-edge={edge}
    onmousedown={startResize}
    role="button"
    tabindex="0"
  ></div>
{/snippet}

{#each edges as edge}
  {@render resizeArea(edge)}
{/each}

<style>
  .window-resizer-left,
  .window-resizer-right,
  .window-resizer-bottom,
  .window-resizer-top,
  .window-resizer-handle {
    position: absolute;
    width: var(--resize-edge-size);
    height: var(--resize-edge-size);
    background-color: transparent;
    z-index: 5000;
    transition: background-color 0.1s ease-in-out;
    &:hover {
      background-color: var(--window-border-color-hover);
    }
    &:active {
      background-color: var(--window-border-color-hover);
    }
  }
  .window-resizer-left {
    cursor: w-resize;
    left: 0;
    top: 0;
    height: 100%;
  }
  .window-resizer-right {
    cursor: e-resize;
    right: 0;
    top: 0;
    height: 100%;
  }
  .window-resizer-bottom {
    cursor: n-resize;
    left: 0;
    bottom: 0;
    width: 100%;
  }
  .window-resizer-top {
    cursor: s-resize;
    left: 0;
    top: 0;
    width: 100%;
  }
  .window-resizer-handle {
    cursor: nwse-resize;
    right: 0;
    bottom: 0;
    width: var(--resize-handle-size);
    height: var(--resize-handle-size);
    background-color: var(--window-border-color);
    transform: translate(50%, 50%) rotate(45deg) scale(1);
    transition:
      background-color 0.1s ease-in-out,
      transform 0.1s ease-in-out;
    &:hover {
      background-color: var(--window-border-color-hover);
      transform: translate(50%, 50%) rotate(45deg) scale(1.5);
    }
    &:active {
      background-color: var(--window-border-color-active);
      transform: translate(50%, 50%) rotate(45deg) scale(1.4);
    }
  }
</style>

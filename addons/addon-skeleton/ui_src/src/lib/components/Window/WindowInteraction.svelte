<script>
  let { resizeable, draggable, dragHandle = null } = $props();
  let sides = ["top", "bottom", "left", "right", "handle"];
  let isResizing = $state(false);
  let side = $state(null);
  let windowSize = { width: 0, height: 0 };
  let windowPosition = { x: 0, y: 0 };
  let minSize = { width: 400, height: 300 };

  function startResize(event) {
    isResizing = true;
    side = event.target.dataset.side;
    windowPosition = { x: window.screenX, y: window.screenY };
    windowSize = { width: window.innerWidth, height: window.innerHeight };
    window.addEventListener("mousemove", doResize);
    window.addEventListener("mouseup", stopResize);
  }

  function stopResize() {
    isResizing = false;
    side = null;
    windowSize = { width: 0, height: 0 };
    windowPosition = { x: 0, y: 0 };
    window.removeEventListener("mousemove", doResize);
    window.removeEventListener("mouseup", stopResize);
  }

  function doResize(event) {
    if (!isResizing) return;
    let width = windowSize.width;
    let height = windowSize.height;

    switch (side) {
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
    pywebview.api.resize(width, height, side);
  }
</script>

<div class="interaction">
  {#if resizeable}
    {#each sides as side}
      <div
        class="resizer-{side}"
        data-side={side}
        onmousedown={startResize}
        tabindex="0"
        role="button"
      ></div>
    {/each}
  {/if}
</div>

<style>
  .interaction {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 500;
    pointer-events: none;
  }
  .resizer-left,
  .resizer-top,
  .resizer-right,
  .resizer-bottom,
  .resizer-handle {
    pointer-events: auto;
    position: absolute;
    width: 0.4rem;
    height: 0.4rem;
    z-index: 600;
    background-color: transparent;
    transition: background-color var(--transition-speed) ease;
    &:hover {
      background-color: var(--lining-color);
    }
    &:active {
      background-color: var(--lining-color-hover);
    }
  }
  .resizer-left {
    cursor: w-resize;
    left: 0;
    top: 0;
    height: 100%;
  }
  .resizer-right {
    cursor: e-resize;
    right: 0;
    top: 0;
    height: 100%;
  }
  .resizer-top {
    cursor: n-resize;
    left: 0;
    top: 0;
    width: 100%;
  }
  .resizer-bottom {
    cursor: s-resize;
    left: 0;
    bottom: 0;
    width: 100%;
  }
  .resizer-handle {
    cursor: nw-resize;
    bottom: 0;
    right: 0;
    width: 1.75rem;
    height: 1.75rem;
    transform: translate(50%, 50%) rotate(45deg);
    z-index: 700;
  }
</style>

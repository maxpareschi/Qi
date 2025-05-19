<script>
  import QiWindowButtonControls from "./QiWindowButtonControls.svelte";
  let {
    icon,
    titleContent,
    draggable = true,
    showClose = true,
    showMinimize = true,
    showMaximize = true,
  } = $props();

  let isMoving = false;
  let mousePosition = { x: 0, y: 0 };
  let dpi = window.devicePixelRatio;

  function startMove(event) {
    if (isMoving) return;
    mousePosition = { x: event.clientX, y: event.clientY };
    isMoving = true;
    window.addEventListener("mousemove", doMove);
    window.addEventListener("mouseup", stopMove);
  }

  function stopMove() {
    if (!isMoving) return;
    isMoving = false;
    mousePosition = { x: 0, y: 0 };
    window.removeEventListener("mousemove", doMove);
    window.removeEventListener("mouseup", stopMove);
  }

  function doMove(event) {
    if (!isMoving) return;
    let x = Math.ceil((event.screenX - mousePosition.x) * dpi);
    let y = Math.ceil((event.screenY - mousePosition.y) * dpi);
    pywebview.api.move(x, y);
  }
</script>

<div class="window-titlebar">
  <div
    class="window-titlebar-icon"
    onmousedown={draggable ? startMove : undefined}
    role="button"
    tabindex="0"
  >
    <img src={icon} alt="Icon" />
  </div>
  <div
    class="window-titlebar-contents"
    onmousedown={draggable ? startMove : undefined}
    role="button"
    tabindex="0"
  >
    {@render titleContent()}
  </div>
  <QiWindowButtonControls {showClose} {showMinimize} {showMaximize} />
</div>

<style>
  .window-titlebar {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    background-color: var(--base-color);
    color: var(--text-color);
    height: var(--title-bar-height);
    min-height: var(--title-bar-height);
    max-height: var(--title-bar-height);
    border: 1px solid var(--window-border-color);
    z-index: 1500;
  }
  .window-titlebar-icon {
    height: 100%;
    padding: 0.5rem;
  }
  .window-titlebar-icon > img {
    height: 100%;
  }
  .window-titlebar-contents {
    height: 100%;
    flex: auto;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
</style>

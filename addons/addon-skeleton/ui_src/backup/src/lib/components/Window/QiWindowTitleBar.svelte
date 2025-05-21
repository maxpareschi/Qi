<script>
  import QiWindowButtonControls from "./QiWindowButtonControls.svelte";
  import QiWindowMenu from "./QiWindowMenu.svelte";
  let {
    menuIcon,
    menuCommands,
    title,
    extraCommands,
    draggable,
    showClose,
    showMinimize,
    showMaximize,
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
  <QiWindowMenu {menuIcon} {menuCommands} {extraCommands} />
  <div
    class="window-titlebar-title"
    onmousedown={draggable ? startMove : undefined}
    role="button"
    tabindex="0"
  >
    {title}
  </div>
  <div class="window-titlebar-buttons">
    {#each extraCommands as command, index}
      <button class="window-titlebar-extra-entry-button">
        {#if command.icon}
          <i class={command.icon}></i>
        {/if}
        {#if command.label}
          {command.label}
        {/if}
      </button>
  {/each}
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
    overflow: hidden;
    background-color: var(--base-color);
    color: var(--text-color);
    height: var(--title-bar-height);
    min-height: var(--title-bar-height);
    max-height: var(--title-bar-height);
    border: 1px solid var(--window-border-color);
    z-index: 1500;
  }
  .window-titlebar-icon,
  .window-titlebar-menu,
  .window-titlebar-title,
  .window-titlebar-buttons {
    display: flex;
    flex-direction: row;
    align-items: center;
    height: 100%;
    padding: 0.5rem;
  }
  .window-titlebar-icon > img {
    height: 100%;
  }
  .window-titlebar-title {
    flex: auto;
    justify-content: center;
    font-weight: bold;
  }
  .window-titlebar-extra-entry-button {
    background-color: transparent;
    color: var(--text-color);
    padding: 0.25rem 0.75rem;
    scale: 1;
    transition: color 0.05s ease-in-out, scale 0.05s ease-in-out;
    &:hover {
      color: var(--text-color-hover);
      scale: 1.2;
    }
    &:active {
      color: var(--text-color-active);
    }
  }
</style>

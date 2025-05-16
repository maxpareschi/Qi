<script>

  import { assets } from "$app/paths";

  let {
    windowTitle = "Application title",
    windowIcon = `${assets}/icons/qi_32.png`,
    confirmOnClose = false,
    isResizable = true,
    showTitlebar = true,
    showMaximize = true,
    showMinimize = true,
    showClose = true,
    showStatusBar = true,
    footerStatusLeft = "info left",
    footerStatusCenter = "info center",
    footerStatusRight = "info right",
    children,
  } = $props();

  let isMaximized = $state(false);

  let showCloseDialog = $state(false);

  function handleMinimize() {
    pywebview.api.minimize_window();
  }

  function handleMaximize() {
    pywebview.api.maximize_window();
    isMaximized = true;
  }

  function handleRestore() {
    pywebview.api.restore_window();
    isMaximized = false;
  }

  function handleClose() {
    pywebview.api.close_window();
  }

  function handleDialogClose() {
    if (confirmOnClose) {
      showCloseDialog = true;
    } else {
      handleClose();
    }
  }

  function handleResize(direction) {
    pywebview.api.resize_window(direction);
  }
</script>

{#if isResizable}
  <div
    class="resize-left"
    onmousedown={() => handleResize("left")}
    role="button"
    tabindex="0"
  ></div>
  <div
    class="resize-right"
    onmousedown={() => handleResize("right")}
    role="button"
    tabindex="0"
  ></div>
  <div
    class="resize-bottom"
    onmousedown={() => handleResize("bottom")}
    role="button"
    tabindex="0"
  ></div>
  <div
    class="resize-top"
    onmousedown={() => handleResize("top")}
    role="button"
    tabindex="0"
  ></div>
  <div
    class="resize-handle"
    onmousedown={() => handleResize("handle")}
    role="button"
    tabindex="0"
  ></div>
{:else}
  <div class="window-border"></div>
{/if}

{#if showTitlebar}
  <div class="window-titlebar">
    <div class="pywebview-drag-region window-titlebar-left">
      <img class="window-titlebar-icon" src={windowIcon} alt="Window logo" />
    </div>
    <div class="pywebview-drag-region window-titlebar-center">
      {windowTitle}
    </div>
    <div class="window-titlebar-right">
      {#if showMinimize}
        <button class="button-minimize" onclick={() => handleMinimize()}>–</button>
      {/if}
      {#if showMaximize}
        <button class="button-maximize" onclick={() => handleMaximize()}>⛶</button>
      {/if}
      {#if showClose}
        <button
          class="button-close"
          onclick={confirmOnClose ? () => handleDialogClose() : () => handleClose()}>✕</button
        >
      {/if}
    </div>
  </div>
{/if}
<div class="window-content">{@render children()}</div>
{#if showStatusBar}
  <div class="pywebview-drag-region window-footer">
    <div class="window-footer-left">Lower left status bar</div>
    <div class="window-footer-center">Lower center status bar</div>
    <div class="window-footer-right">Lower right status bar</div>
  </div>
{/if}
{#if confirmOnClose}
  <div
    id="close-overlay"
    class="close-overlay {showCloseDialog ? 'close-overlay-active' : ''}"
    onclick={() => (showCloseDialog = false)}
    onkeydown={() => {
      return;
    }}
    role="button"
    tabindex="0"
  ></div>
  <div
    id="close-dialog"
    class="close-dialog {showCloseDialog ? 'close-dialog-active' : ''}"
  >
    <p style="color: var(--accent-color)"><b>Confirm close</b></p>
    <p>Are you sure you want to close this window?</p>
    <div class="close-dialog-buttons">
      <button
        class="button-cancel-dialog"
        onclick={() => (showCloseDialog = false)}
      >
        Cancel
      </button>
      <button class="button-close-dialog" onclick={showCloseDialog ? handleClose : () => {return}}> Close </button>
    </div>
  </div>
{/if}

<style>
  .window-border {
    position: absolute;
    pointer-events: none;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border: 1px solid var(--window-border-color);
    background-color: transparent;
    z-index: 500;
  }

  .window-titlebar,
  .window-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 2.75rem;
    min-height: 2.75rem;
    max-height: 2.75rem;
    gap: 0.5rem;
    text-shadow: 0 0.2rem 0.15rem rgba(0, 0, 0, 0.25);
    background-color: var(--window-frame-color);
    border: 1px solid var(--window-border-color);
  }

  /* Titlebar */

  .window-titlebar > div {
    height: 100%;
    align-content: center;
  }

  .window-titlebar-icon {
    height: 100%;
    width: 100%;
    padding: 0.5rem;
    filter: drop-shadow(0 0.2rem 0.1rem rgba(0, 0, 0, 0.25));
    z-index: 7000;
  }

  .window-titlebar-center {
    flex: auto;
    z-index: 7000;
    /*font-weight: bold;*/
  }

  .window-titlebar-left,
  .window-titlebar-right {
    z-index: 7000;
  }

  .window-titlebar-right {
    display: flex;
    z-index: 2000;
  }

  /* Titlebar buttons */

  .button-close,
  .button-maximize,
  .button-minimize {
    cursor: pointer;
    user-select: none;
    color: var(--text-color);
    background-color: transparent;
    border: none;
    padding: 0 1.5rem;
    transition: background-color 0.1s ease-in-out;
    text-shadow: 0 0.15rem 0.15rem rgba(0, 0, 0, 1);
    overflow: hidden;
    &:hover {
      color: var(--text-color-hover);
      background-color: var(--base-color-hover);
    }
    &:active {
      color: var(--text-color-active);
      background-color: var(--base-color-active);
    }
  }

  .button-close {
    &:hover {
      background-color: var(--error-color-hover);
    }
    &:active {
      background-color: var(--error-color-active);
    }
  }

  /* Content */

  .window-content {
    flex: auto;
    padding: 0.5rem;
    overflow: auto;
    background-color: var(--bg-color);
  }

  /* Footer */

  .window-footer {
    height: 1.75rem;
    min-height: 1.75rem;
    max-height: 1.75rem;
    font-size: 0.75rem;
    padding: 0 0.5rem;
    font-family: "FiraCode Nerd Font Light", monospace;
  }

  /* Resize handles */

  .resize-bottom,
  .resize-right,
  .resize-top,
  .resize-left {
    position: absolute;
    width: 0.4rem;
    height: 0.4rem;
    z-index: 1400;
    background-color: transparent;
    transform: scale(1);
    transition: background-color 0.1s ease-in-out;
    &:hover {
      background-color: var(--window-border-color);
    }
    &:active {
      background-color: var(--window-border-color-active);
    }
  }

  .resize-left {
    cursor: w-resize;
    height: 100vh;
    left: 0;
    top: 0;
    border-left: 1px solid var(--window-border-color);
  }

  .resize-right {
    cursor: e-resize;
    height: 100vh;
    right: 0;
    top: 0;
    border-right: 1px solid var(--window-border-color);
  }

  .resize-bottom {
    cursor: s-resize;
    width: 100vw;
    bottom: 0;
    left: 0;
    border-bottom: 1px solid var(--window-border-color);
  }

  .resize-top {
    cursor: n-resize;
    width: 100vw;
    top: 0;
    left: 0;
    border-top: 1px solid var(--window-border-color);
  }

  .resize-handle {
    cursor: nwse-resize;
    position: absolute;
    right: 0;
    bottom: 0;
    width: 1rem;
    height: 1rem;
    transform: translate(0.5rem, 0.5rem) scale(1.1) rotate(45deg);
    background-color: var(--window-border-color);
    transition:
      transform 0.1s ease-in-out,
      background-color 0.1s ease-in-out;
    z-index: 1500;
    &:hover {
      background-color: var(--window-border-color-hover);
      transform: translate(0.5rem, 0.5rem) scale(2) rotate(45deg);
    }
    &:active {
      background-color: var(--window-border-color-active);
      transform: translate(0.5rem, 0.5rem) scale(1.5) rotate(45deg);
    }
  }

  /* Close dialog */

  .close-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 2000;
    background-color: rgba(0, 0, 0, 0);
    border: 0px solid rgba(0, 0, 0, 0);
    transition:
      background-color 0.3s ease-in-out,
      border 0.3s ease-in-out;
    pointer-events: none;
  }

  .close-dialog {
    position: absolute;
    width: 100%;
    height: 4.5rem;
    bottom: -4.5rem;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    z-index: 3000;
    background-color: var(--window-frame-color);
    border: 1px solid var(--window-border-color);
    transition: bottom 0.3s ease-in-out;
  }

  .close-overlay-active {
    pointer-events: auto;
    background-color: rgba(0, 0, 0, 0.7);
    border: 1px solid var(--window-border-color);
  }

  .close-dialog-active {
    bottom: 0;
  }

  .close-dialog > * {
    padding: 0 1rem;
  }

  .close-dialog-buttons {
    display: flex;
    flex-direction: row;
    gap: 1rem;
  }

  .close-dialog-buttons > button {
    /* color: var(--text-color);*/
    border-radius: 0.5rem;
    border: 1px solid var(--reactive-color-border);
    transition: background-color 0.1s ease-in-out;
    &:hover {
      color: var(--text-color-hover);
    }
  }

  .button-cancel-dialog {
    background-color: var(--base-color);
    &:hover {
      background-color: var(--base-color-hover);
    }

    &:active {
      background-color: var(--base-color-active);
    }
  }

  .button-close-dialog {
    background-color: var(--error-color);

    &:hover {
      background-color: var(--error-color-hover);
    }
    &:active {
      background-color: var(--error-color-active);
    }
  }
</style>

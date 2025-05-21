<script>
  import QiWindowResizer from "./QiWindowResizer.svelte";
  import QiWindowTitleBar from "./QiWindowTitleBar.svelte";
  import QiWindowStatusBar from "./QiWindowStatusBar.svelte";
  let {
    title,
    menuIcon,
    resizeable,
    draggable,
    showTitlebar,
    showStatusbar,
    showClose,
    showMinimize,
    showMaximize,
    edges,
    menuCommands,
    extraCommands,
    status,
    statusExtra,
    children,
  } = $props();
</script>

<div class="window-container">
  {#if showTitlebar}
    <QiWindowTitleBar
      {draggable}
      {showMinimize}
      {showMaximize}
      {showClose}
      {menuIcon}
      {menuCommands}
      {title}
      {extraCommands}
    />
  {/if}

  <div class="window-content">
    {@render children?.()}
  </div>

  {#if showStatusbar}
    <QiWindowStatusBar {status} {statusExtra} />
  {/if}
</div>

{#if resizeable}
  <QiWindowResizer {edges} />
{/if}

<div class="window-border"></div>

<style>
  .window-container {
    display: flex;
    flex-direction: column;
    height: 100%;
  }
  .window-content {
    padding: 0.5rem;
    flex: auto;
    overflow: auto;
    background-color: var(--bg-color);
  }
  .window-border {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border: 1px solid var(--window-border-color);
    pointer-events: none;
    z-index: 10000;
  }
</style>

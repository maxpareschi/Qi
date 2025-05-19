<script>
  import QiWindowResizer from "./QiWindowResizer.svelte";
  import QiWindowTitleBar from "./QiWindowTitleBar.svelte";
  import QiWindowStatusBar from "./QiWindowStatusBar.svelte";
  let {
    icon,
    title = "Test window title",
    resizeable = true,
    draggable = true,
    showTitlebar = true,
    showStatusbar = true,
    showClose = true,
    showMinimize = true,
    showMaximize = true,
    status = "megatest",
    statusExtra = "megatest2",
    children,
  } = $props();
</script>

<div class="window-border"></div>

{#if resizeable}
  <QiWindowResizer />
{/if}

<div class="window-container">
  {#if showTitlebar}
    <QiWindowTitleBar
      {icon}
      {draggable}
      {showMinimize}
      {showMaximize}
      {showClose}
    >
      {#snippet titleContent()}
        {title}
      {/snippet}
    </QiWindowTitleBar>
  {/if}

  <div class="window-content">
    {@render children()}
  </div>

  {#if showStatusbar}
    <QiWindowStatusBar>
      {#snippet statusContent()}
        {status}
      {/snippet}
      {#snippet statusExtraContent()}
        {statusExtra}
      {/snippet}
    </QiWindowStatusBar>
  {/if}
</div>

<style>
  .window-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
  }
  .window-content {
    padding: 0.5rem;
    width: 100%;
    flex: auto;
    overflow: auto;
    background-color: var(--bg-color);
  }
  .window-border {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border: 1px solid var(--window-border-color);
    pointer-events: none;
    z-index: 7000;
  }
</style>

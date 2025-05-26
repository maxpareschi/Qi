<script>
  import WindowTitleBar from "./WindowTitleBar.svelte";
  import WindowStatusBar from "./WindowStatusBar.svelte";
  import WindowInteraction from "./WindowInteraction.svelte";

  let { windowState, windowFlags, children } = $props();
  
</script>

<div class="window">
  {#if windowFlags.showAppBorder}
    <div class="window-app-border border"></div>
  {/if}
  {#if windowFlags.resizeable && !windowState.isMaximized}
    <WindowInteraction {...windowState} {...windowFlags} />
  {/if}
  {#if windowFlags.showTitlebar}
    <WindowTitleBar {...windowState} {...windowFlags} />
  {/if}
  <div class="window-content">
    {@render children()}
  </div>
  {#if windowFlags.showStatusbar}
    <WindowStatusBar {...windowState} {...windowFlags} />
  {/if}
</div>

<style>
  .window {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
  }
  .window-content {
    flex: auto;
    overflow: auto;
    padding: 1rem;
    background-color: var(--bg-color);
  }
  .window-app-border {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 10000;
    pointer-events: none;
  }
</style>

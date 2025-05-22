<script>
  import WindowTitleBar from "./WindowTitleBar.svelte";
  import WindowStatusBar from "./WindowStatusBar.svelte";
  import WindowInteraction from "./WindowInteraction.svelte";
  let { windowSettings, children} = $props();

  let isMaximized = $state(false);
</script>

<div class="window">
  {#if windowSettings.resizeable && !isMaximized}
    <WindowInteraction {...windowSettings} />
  {/if}
  {#if windowSettings.showTitlebar}
    <WindowTitleBar {...windowSettings} bind:isMaximized={isMaximized} />
  {/if}
  <div class="window-content">
    {@render children()}
  </div>
  {#if windowSettings.showStatusbar}
    <WindowStatusBar {...windowSettings} />
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
</style>

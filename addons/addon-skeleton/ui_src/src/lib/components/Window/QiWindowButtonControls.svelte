<script>
  let { showClose = true, showMinimize = true, showMaximize = true } = $props();

</script>

<div class="window-button-controls">
  {#if showMinimize}
    <button class="window-button-controls-minimize" onclick={() => pywebview.api.minimize()}>–</button>
  {/if}
  {#if showMaximize}
    <button class="window-button-controls-maximize" onclick={() => pywebview.api.maximize()}>⛶</button>
  {/if}
  {#if showClose}
    <button class="window-button-controls-close" onclick={() => pywebview.api.close()}>✕</button>
  {/if}
</div>

<style>
  .window-button-controls {
    height: 100%;
    display: flex;
    flex-direction: row;
    align-items: flex-end;
    justify-content: center;
  }
  .window-button-controls-minimize,
  .window-button-controls-maximize,
  .window-button-controls-close {
    height: 100%;
    background-color: transparent;
    text-shadow: 0 0.1rem 0.1rem black;
    transition: background-color 0.1s ease-in-out;
    &:hover {
      background-color: var(--base-color-hover);
    }
    &:active {
      background-color: var(--base-color-active);
    }
  }
  .window-button-controls-close {
    &:hover {
      background-color: var(--error-color-hover);
    }
    &:active {
      background-color: var(--error-color-active);
    }
  }
</style>

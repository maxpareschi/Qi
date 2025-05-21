<script>
  let { showMinimize, showMaximize, showClose } = $props();
</script>

{#if showMinimize || showMaximize || showClose}
  <div class="controls border">
    {#if showMinimize}
      <button
        class="minimize-button"
        onclick={() => {
          if (typeof pywebview !== "undefined") {
            pywebview.api.minimize();
          }
        }}
        aria-label="Minimize"
      >
        <i class="fa-solid fa-window-minimize"></i>
      </button>
    {/if}
    {#if showMaximize}
      <button
        class="maximize-button"
        onclick={() => {
          if (typeof pywebview !== "undefined") {
            pywebview.api.maximize();
          }
        }}
        aria-label="Maximize"
      >
        <i class="fa-solid fa-expand"></i>
      </button>
    {/if}
    {#if showClose}
      <button
        class="close-button"
        onclick={() => {
          if (typeof pywebview !== "undefined") {
            pywebview.api.close();
          }
        }}
        aria-label="Close"
      >
        <i class="fa-solid fa-xmark"></i>
      </button>
    {/if}
  </div>
{/if}

<style>
  .controls {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-end;
    margin: 0.5rem;
    margin-left: 1rem;
    border-radius: 0.25rem;
  }
  .controls button {
    padding: 0.25rem 1rem;
  }
  .close-button {
    &:hover {
      color: var(--text-color-hover);
      background-color: var(--error-color);
    }
    &:active {
      color: var(--text-color-active);
      background-color: var(--error-color-active);
    }
  }
</style>

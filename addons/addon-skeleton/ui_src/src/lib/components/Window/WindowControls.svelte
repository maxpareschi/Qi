<script>
  import { minimizeWindow, maximizeWindow, closeWindow } from "$lib/scripts/qi.windowScripts.svelte";
  import { windowState } from "$lib/scripts/qi.windowState.svelte";

  let {
    data,
    showMinimize,
    showMaximize,
    showClose,
  } = $props();

</script>

{#if showMinimize || showMaximize || showClose}
  <div class="controls">
    {#if showMinimize}
      <button
        class="minimize-button"
        onclick={minimizeWindow}
        aria-label="Minimize"
      >
        <i class="fa-solid fa-window-minimize"></i>
      </button>
    {/if}
    {#if showMaximize}
      <button
        class="maximize-button"
        onclick={maximizeWindow}
        aria-label="Maximize"
      >
        {#if windowState.isMaximized}
          <i class="fa-solid fa-compress"></i>
        {:else}
          <i class="fa-solid fa-expand"></i>
        {/if}
      </button>
    {/if}
    {#if showClose}
      <button
        class="close-button"
        onclick={closeWindow}
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
    margin-left: 1.5rem;
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

<script>
  let {
    showMinimize,
    showMaximize,
    showClose,
  } = $props();
</script>

<div class="controls">
  {#if showMinimize}
    <button
      class="control-button"
      onclick={() => {
        window.minimize();
      }}
      aria-label="Minimize"
    >
      <i class="fa-solid fa-window-minimize"></i>
    </button>
  {/if}
  {#if showMaximize}
    <button
      class="control-button"
      onclick={() => {
        window.maximize();
      }}
      aria-label="Maximize"
    >
      <i class="fa-solid fa-expand"></i>
    </button>
  {/if}
  {#if showClose}
    <button
      class="control-button"
      onclick={() => {
        window.close();
      }}
      aria-label="Close"
    >
      <i class="fa-solid fa-xmark"></i>
    </button>
  {/if}
</div>

<style>
  .controls {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
  }
  .control-button {
    padding: 0.5rem 2rem;
    border: none;
    background-color: transparent;
    cursor: pointer;
  }
</style>
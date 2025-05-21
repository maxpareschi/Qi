<script>
  import WindowTitleBar from "./WindowTitleBar.svelte";
  let { windowSettings, children } = $props();
</script>

<div class="window">
  <WindowTitleBar {...windowSettings} />

  <div class="window-content">
    {@render children()}
  </div>

  <div class="statusbar"></div>
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

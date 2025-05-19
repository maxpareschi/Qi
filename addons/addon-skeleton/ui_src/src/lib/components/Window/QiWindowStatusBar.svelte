<script>
  let { statusContent = "", statusExtraContent = "" } = $props();
</script>

<div class="window-statusbar">
  <div class="window-statusbar-status">
    {@render statusContent()}
  </div>
  <div class="window-statusbar-extra-status">
    {@render statusExtraContent()}
  </div>
</div>

<style>
  .window-statusbar {
    font-family: "FiraCode Nerd Font Light", monospace;
    font-size: 0.75rem;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    width: 100%;
    background-color: var(--base-color);
    color: var(--text-color);
    height: var(--status-bar-height);
    min-height: var(--status-bar-height);
    max-height: var(--status-bar-height);
    border: 1px solid var(--window-border-color);
    z-index: 1500;
  }
  .window-statusbar-status,
  .window-statusbar-extra-status {
    height: 100%;
    padding: 0 0.5rem;
    align-content: center;
  }
  .window-statusbar-extra-status {
    padding-right: 1rem;
  }
</style>

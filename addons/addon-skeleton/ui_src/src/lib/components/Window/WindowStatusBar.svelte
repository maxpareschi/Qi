<script>
  let { showStatusbar, statusMessageMain, statusMessageSub } = $props();
</script>

{#if showStatusbar}
  <div class="statusbar">
    <div class="message-main">{statusMessageMain}</div>
    <div class="message-sub">
      {statusMessageSub} <i class="link-icon fa-solid fa-link"></i>
    </div>
  </div>
{/if}

<style>
  .statusbar {
    /*font-family: var(--font-family-monospace);*/
    font-size: var(--font-size-xsmall);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem;
    height: var(--statusbar-height);
    max-height: var(--statusbar-height);
    min-height: var(--statusbar-height);
    background-color: var(--base-color);
    border-top: 1px solid var(--lining-color);
  }
  .link-icon {
    color: var(--success-color);
  }
</style>


<script>
  let { fastAccessMenu } = $props();
</script>

{#if fastAccessMenu.length > 0}
  <div class="menu">
    {#each fastAccessMenu as item, index}
      {#if item.icon}
        <button
          class="button-icon"
          onclick={item.action}
          aria-label={item.label}
        >
          <i class={item.icon}></i>
        </button>
      {/if}
    {/each}
  </div>
{/if}

<style>
  .menu {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-end;
    height: 100%;
    gap: 1.5rem;
    padding: 0.5rem 1rem;
    overflow: hidden;
  }
  .menu > button {
    padding: 0;
  }
</style>

<script>
  let { resizeable, draggable, dragHandle = null } = $props();
  let sides = ["top", "bottom", "left", "right", "handle"];
</script>

<div class="interaction">
  {#if resizeable}
    {#each sides as side}
      <div class="resizer-{side}"></div>
    {/each}
  {/if}
</div>

<style>
  .interaction {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
  }
  .resizer-left,
  .resizer-top,
  .resizer-right,
  .resizer-bottom,
  .resizer-handle {
    position: absolute;
    width: 0.4rem;
    height: 0.4rem;
    z-index: 200;
    background-color: transparent;
    transition: background-color 0.1s ease;
    &:hover {
      background-color: var(--base-color-hover);
    }
    &:active {
      background-color: var(--base-color-active);
    }
  }
  .resizer-left {
    left: 0;
    top: 0;
    height: 100%;
  }
  .resizer-right {
    right: 0;
    top: 0;
    height: 100%;
  }
  .resizer-top {
    left: 0;
    top: 0;
    width: 100%;
  }
  .resizer-bottom {
    left: 0;
    bottom: 0;
    width: 100%;
  }
  .resizer-handle {
    bottom: 0;
    right: 0;
  }
</style>

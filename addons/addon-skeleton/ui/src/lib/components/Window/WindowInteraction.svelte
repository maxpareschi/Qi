<script>
  import { startResize } from "$lib/scripts/qi.windowScripts.svelte";
  let { resizeable, draggable, resizeSides } = $props();
</script>

<div class="interaction">
  {#if resizeable}
    {#each resizeSides as side}
      <div
        class="resizer-{side}"
        data-side={side}
        onmousedown={startResize}
        tabindex="0"
        role="button"
      ></div>
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
    z-index: 500;
    pointer-events: none;
  }
  .resizer-left,
  .resizer-top,
  .resizer-right,
  .resizer-bottom,
  .resizer-bottom-right,
  .resizer-bottom-left {
    pointer-events: auto;
    position: absolute;
    width: 0.4rem;
    height: 0.4rem;
    z-index: 600;
    background-color: transparent;
    transition: background-color var(--transition-speed) ease;
    &:hover {
      background-color: var(--lining-color);
    }
    &:active {
      background-color: var(--lining-color-hover);
    }
  }
  .resizer-left {
    cursor: w-resize;
    left: 0;
    top: 0;
    height: 100%;
  }
  .resizer-right {
    cursor: e-resize;
    right: 0;
    top: 0;
    height: 100%;
  }
  .resizer-top {
    cursor: n-resize;
    left: 0;
    top: 0;
    width: 100%;
  }
  .resizer-bottom {
    cursor: s-resize;
    left: 0;
    bottom: 0;
    width: 100%;
  }
  .resizer-bottom-right{
    cursor: nw-resize;
    bottom: 0;
    right: 0;
    width: 1.75rem;
    height: 1.75rem;
    transform: translate(50%, 50%) rotate(45deg);
    z-index: 700;
  }
  .resizer-bottom-left{
    cursor: ne-resize;
    bottom: 0;
    left: 0;
    width: 1.75rem;
    height: 1.75rem;
    transform: translate(-50%, 50%) rotate(45deg);
    z-index: 700;
  }
</style>

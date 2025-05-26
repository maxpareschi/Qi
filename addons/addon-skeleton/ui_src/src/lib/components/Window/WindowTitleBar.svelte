<script>
  import { startMove, stopMove, doMove } from "$lib/scripts/qi.windowScripts.svelte";
  import { fly, fade } from "svelte/transition";
  import { onMount } from "svelte";
  import { windowState } from "$lib/scripts/qi.windowState.svelte";
  import WindowAppMenu from "./WindowAppMenu.svelte";
  import WindowFastaccessMenu from "./WindowFastaccessMenu.svelte";
  import WindowControls from "./WindowControls.svelte";
  
  let {
    showTitlebar,
    icon,
    title,
    appMenu,
    appMenuOpenedAtStart,
    fastAccessMenu,
    showMinimize,
    showMaximize,
    showClose,
    draggable,
  } = $props();

  let draggableElements = $state([]);

  let titleRef = null;
  let titlebarRef = null;
  let titleTextRef = null;

  onMount(() => {
    draggableElements.push(titlebarRef);
    draggableElements.push(titleRef);
    draggableElements.push(titleTextRef);
  });
</script>

<div
  class="titlebar"
  onmousedown={(e) => {
    if (draggable && draggableElements.includes(e.target) && !windowState.isMaximized) {
      startMove(e);
    }
  }}
  role="button"
  tabindex="0"
  bind:this={titlebarRef}
>
  <WindowAppMenu {icon} {appMenu} {appMenuOpenedAtStart} />

  <div class="title" bind:this={titleRef}>
    <div
      class="title-text {windowState.isAppMenuOpen ? 'title-text-open' : ''}"
      bind:this={titleTextRef}
    >
      {title}
    </div>
  </div>

  <WindowFastaccessMenu {fastAccessMenu} />
  <WindowControls
    {showMinimize}
    {showMaximize}
    {showClose}
  />
</div>

<style>
  .titlebar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: var(--titlebar-height);
    max-height: var(--titlebar-height);
    min-height: var(--titlebar-height);
    background-color: var(--base-color);
    border-bottom: 1px solid var(--lining-color);
  }
  .title {
    position: relative;
    flex: auto;
    height: 100%;
    color: var(--text-color-hover);
  }
  .title-text {
    position: absolute;
    left: 0;
    height: 100%;
    width: fit-content;
    white-space: nowrap;
    padding: 0 0.5rem;
    transform: translateX(0);
    align-content: center;
    background-color: var(--base-color);
    transition:
      transform var(--transition-speed) ease-in-out,
      left var(--transition-speed) ease-in-out;
  }
  .title-text-open {
    left: 50%;
    transform: translateX(-50%);
    margin-right: auto;
  }
</style>

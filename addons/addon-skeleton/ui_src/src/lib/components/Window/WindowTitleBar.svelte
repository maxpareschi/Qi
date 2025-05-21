<script>
  import WindowAppMenu from "./WindowAppMenu.svelte";
  import WindowFastaccessMenu from "./WindowFastaccessMenu.svelte";
  import WindowControls from "./WindowControls.svelte";
  import { fly, fade } from "svelte/transition";
  import { onMount } from "svelte";
  let {
    showTitlebar,
    icon,
    title,
    appMenu,
    appMenuStartOpened,
    fastAccessMenu,
    showMinimize,
    showMaximize,
    showClose,
  } = $props();

  let isDragging = $state(false);
  let isMounted = $state(false);
  let isAppMenuOpen = $state(false);
</script>

<div class="titlebar">
  <WindowAppMenu
    {icon}
    {appMenu}
    {appMenuStartOpened}
    bind:isAppMenuOpen
  />

  <div class="title">
    <div class="title-text {isAppMenuOpen ? 'title-text-open' : ''}">
      <p>{title}</p>
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
    z-index: 10;
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
      transform 0.2s ease-in-out,
      left 0.2s ease-in-out;
  }
  .title-text-open {
    left: 50%;
    transform: translateX(-50%);
    margin-right: auto;
  }
</style>

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
    draggable,
    isMaximized = $bindable(false),
  } = $props();

  let isMoving = $state(false);
  let isAppMenuOpen = $state(false);

  let mousePosition = { x: 0, y: 0 };

  let draggableElements = $state([]);

  let titleRef = null;
  let titlebarRef = null;
  let titleTextRef = null;

  onMount(() => {
    draggableElements.push(titlebarRef);
    draggableElements.push(titleRef);
    draggableElements.push(titleTextRef);
  });

  function startMove(event) {
    if (isMoving) return;
    mousePosition = { x: event.clientX, y: event.clientY };
    isMoving = true;
    window.addEventListener("mousemove", doMove);
    window.addEventListener("mouseup", stopMove);
  }

  function stopMove() {
    if (!isMoving) return;
    isMoving = false;
    mousePosition = { x: 0, y: 0 };
    window.removeEventListener("mousemove", doMove);
    window.removeEventListener("mouseup", stopMove);
  }

  function doMove(event) {
    if (!isMoving) return;
    let x = Math.ceil(event.screenX - mousePosition.x);
    let y = Math.ceil(event.screenY - mousePosition.y);
    pywebview.api.move(x, y);
  }
</script>

<div
  class="titlebar"
  onmousedown={(e) => {
    if (draggable && draggableElements.includes(e.target) && !isMaximized) {
      startMove(e);
    }
  }}
  role="button"
  tabindex="0"
  bind:this={titlebarRef}
>
  <WindowAppMenu {icon} {appMenu} {appMenuStartOpened} bind:isAppMenuOpen />

  <div class="title" bind:this={titleRef}>
    <div
      class="title-text {isAppMenuOpen ? 'title-text-open' : ''}"
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
    bind:isMaximized={isMaximized}
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

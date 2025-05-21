<script>
  import { scale, fly } from "svelte/transition";
  import { cubicOut, linear } from "svelte/easing";
  let { menuIcon, menuCommands, extraCommands } = $props();
  let isOpen = $state(false);

  function flyStaggered(node, params) {
    const duration = params.duration || 250;
    const stagger = params.stagger || 400;
    const index = params.index || 1;
    const x = params.x || 5;
    const units = params.units || "rem";
    return {
      delay: params.delay || 0,
      duration: duration + index * stagger,
      easing: params.easing || cubicOut,
      css: (t, u) => {
        return `
          transform: translateX(${t * x - x}rem);
		  opacity: ${t};
		  flex-grow: ${t};
		`;
      },
    };
  }

  const toggleMenu = () => {
    if (menuCommands.length > 0) {
      isOpen = !isOpen;
      console.log(isOpen);
    }
  };
</script>

<div class="window-titlebar-menu">
  <button class="window-titlebar-icon-button" onclick={toggleMenu}>
    <img src={menuIcon} alt="Icon" draggable="false" height="100%" />
  </button>
    {#each menuCommands as command, index}
      {#if isOpen}
        <button class="window-titlebar-menu-entry-button">
          {#if command.icon}
            <i class={command.icon}></i>
          {/if}
          {#if command.label}
            {command.label}
          {/if}
        </button>
      {/if}
    {/each}
</div>

<style>
  .window-titlebar-menu {
    display: flex;
    flex-direction: row;
    align-items: center;
    height: 100%;
  }
  .window-titlebar-icon-button {
    height: 100%;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem;
    background-color: transparent;
  }
  .window-titlebar-icon-button > img {
    scale: 1;
    z-index: 100;
    filter: brightness(1);
    transition:
      scale 0.1s ease-in-out,
      filter 0.1s ease-in-out;
    &:hover {
      filter: brightness(1.1);
      scale: 1.2;
    }
    &:active {
      filter: brightness(1.2);
      scale: 1.1;
    }
  }
  .window-titlebar-menu-entry-container {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.5rem;
    width: 0;
    max-width: 0;
    overflow: hidden;
    transition: width 3s ease-in-out, max-width 3s ease-in-out;
  }
  .openmenu {
    width: 100%;
    max-width: 100%;
  }
  .window-titlebar-menu-entry-button {
    display: flex;
    flex-direction: row;
    align-items: center;
    font-size: 0.85rem;
    gap: 0.25rem;
    background-color: transparent;
    color: var(--text-color);
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    flex-grow: 0;
    transform: translateX(0);
    transition:
      background-color 0.1s ease-in-out,
      color 0.1s ease-in-out,
      flex-grow 0.1s ease-in-out;
    &:hover {
      background-color: var(--base-color-hover);
      color: var(--text-color-hover);
    }
    &:active {
      background-color: var(--base-color-active);
      color: var(--text-color-active);
    }
  }
</style>

<script>
  import { fly } from "svelte/transition";
  import { onMount } from "svelte";
  import { assets } from "$app/paths";
  import { windowState } from "$lib/states/qi.windowState.svelte";
  let {
    icon,
    appMenu,
    appMenuOpenedAtStart,
  } = $props();

  let transitionSpeed = $state(150);

  onMount(() => {
    windowState.isAppMenuOpen = appMenuOpenedAtStart;
    transitionSpeed = window
      .getComputedStyle(document.documentElement)
      .getPropertyValue("--transition-speed");
    if (transitionSpeed.includes("ms")) {
      transitionSpeed = transitionSpeed.replace("ms", "");
    } else if (transitionSpeed.includes("s")) {
      transitionSpeed = transitionSpeed.replace("s", "") * 1000;
    }
    transitionSpeed = parseInt(transitionSpeed);
  });

</script>

<div class="menu-button">
  {#if appMenu.length > 0}
    <button
      class="button-image"
      onclick={() => {
        windowState.isAppMenuOpen = !windowState.isAppMenuOpen;
      }}
    >
      {#if icon.includes("/") || icon.includes("\\")}
        <img src={icon} alt="Qi" draggable="false" />
      {:else}
        <i class={icon}></i>
      {/if}
    </button>
  {:else if icon.includes("/") || icon.includes("\\")}
    <img src={icon} alt="Qi" draggable="false" />
  {:else}
    <i class={icon}></i>
  {/if}
</div>

<div class="menu-content {windowState.isAppMenuOpen ? 'menu-opened' : ''}">
  {#each appMenu as item, index}
    {#if windowState.isAppMenuOpen}
      <button
        onclick={item.action}
        aria-label={item.label}
        transition:fly={{
          delay: (appMenu.length - index) * 50,
          x: -200,
          duration: transitionSpeed,
        }}
      >
        {#if item.icon}
          <i class={item.icon}></i>
        {/if}
        {item.label}
      </button>
    {/if}
  {/each}
</div>

<style>
  .menu-button {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .menu-button * {
    height: 100%;
    padding: 0rem;
    align-content: center;
  }
  .menu-button img {
    padding: 0.5rem;
  }
  .menu-button i {
    padding: 0.5rem 1rem;
  }
  .menu-content {
    position: relative;
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.5rem;
    width: 0;
    overflow: hidden;
    transition: width var(--transition-speed) ease;
  }
  .menu-opened {
    width: calc-size(min-content, size);
  }
  .menu-content * {
    font-size: var(--font-size-small);
  }
</style>

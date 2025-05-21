<script>
  import { fly } from "svelte/transition";
  import { onMount } from "svelte";
  import { assets } from "$app/paths";

  let {
    icon,
    appMenu,
    appMenuStartOpened = false,
    isAppMenuOpen = $bindable(false),
  } = $props();
  let menuOpen = $state(false);
  let transitionSpeed = 100;

  onMount(() => {
    menuOpen = appMenuStartOpened;
  });

  $effect(() => {
    isAppMenuOpen = menuOpen;
  });
</script>

<div class="menu-button">
  {#if appMenu.length > 0}
    <button
      class="button-image"
      onclick={() => {
        menuOpen = !menuOpen;
      }}
    >
      {#if icon.includes("/") || icon.includes("\\")}
        <img src={icon} alt="Qi" />
      {:else}
        <i class={icon}></i>
      {/if}
    </button>
  {:else if icon.includes("/") || icon.includes("\\")}
    <img src={icon} alt="Qi" />
  {:else}
    <i class={icon}></i>
  {/if}
</div>

<div
  class="menu-content {menuOpen ? 'menu-opened' : ''}"
  style="--transition-speed: {transitionSpeed}ms"
>
  {#each appMenu as item, index}
    {#if menuOpen}
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
    height: 100%;
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

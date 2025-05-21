<script>
  import { fly } from "svelte/transition";
  import { onMount } from "svelte";
  import { assets } from "$app/paths";

  let { icon, appMenu, isAppMenuOpen = $bindable(false) } = $props();

  let menuOpen = $state(false);
  let transitionSpeed = 200;
</script>

<div class="menu-button">
  {#if appMenu.length > 0}
    <button
      class="button-icon"
      onclick={() => {
        menuOpen = !menuOpen;
        isAppMenuOpen = menuOpen;
      }}
    >
      {#if icon.includes("/") || icon.includes("\\")}
        <img class="menu-image" src={icon} alt="Icon" />
      {:else}
        <i class="{icon} menu-icon"></i>
      {/if}
    </button>
  {:else if icon.includes("/") || icon.includes("\\")}
    <img class="menu-icon" src={icon} alt="Icon" />
  {:else}
    <i class="menu-icon icon {icon}"></i>
  {/if}
</div>

<div
  class="menu-content {menuOpen ? 'menu-opened' : ''}"
  style="--transition-speed: {transitionSpeed}ms"
>
  {#each appMenu as item, index}
    {#if menuOpen}
      <button
        class="button-base menu-entry"
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
  .menu-button,
  .button-icon,
  .menu-image,
  .menu-icon {
    height: 100%;
    padding: 0rem;
    align-content: center;
  }
  .menu-image {
    padding: 0.5rem;
  }
  .menu-icon {
    padding: 0.5rem 1rem;
  }
  .menu-content {
    position: relative;
    display: flex;
    flex-direction: row;
    align-items: center;
    width: 0;
    height: 100%;
    overflow: hidden;
    transition:
      width var(--transition-speed) ease;
  }
  .menu-entry {
    padding: 0.25rem 0.75rem;
    font-size: 0.95rem;
  }
  .menu-opened {
    width: calc-size(min-content, size);
  }
</style>

<script>
  import { windowSettings } from "$lib/components/Window/WindowSettings.svelte";
  import Window from "$lib/components/Window/Window.svelte";
  import { assets } from "$app/paths";
  
  let { children } = $props();
</script>

<Window {windowSettings}>
  {@render children()}
</Window>

<style>
  @import url("/styles/root.css");
</style>

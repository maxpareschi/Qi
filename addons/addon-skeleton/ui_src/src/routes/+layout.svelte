<script>
  import { windowState, windowFlags } from "$lib/states/qi.windowState.svelte";
  import Window from "$lib/components/Window/Window.svelte";

  let { children } = $props();
</script>

<Window {windowState} {windowFlags}>
  {@render children()}
</Window>

<style>
  @import url("/styles/root.css");
</style>

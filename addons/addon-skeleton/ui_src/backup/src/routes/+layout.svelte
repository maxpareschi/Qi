<script>
  import QiWindow from "$lib/components/Window/QiWindow.svelte";
  import { windowState } from "$lib/components/Window/QiWindowState.svelte.js";
  
  let { children } = $props();

</script>

<QiWindow
  {...windowState}>
  {@render children()}
</QiWindow>

<style>
</style>

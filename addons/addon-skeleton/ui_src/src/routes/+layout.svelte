<script>
  import { initQiConnection, qiConnection } from "$lib/stores/qi.connection.svelte";
  import { windowSettings } from "$lib/components/Window/WindowSettings.svelte";
  import Window from "$lib/components/Window/Window.svelte";
  import { onMount } from "svelte";
  
  let { children } = $props();

  onMount(() => {
    windowSettings.title = "Qi - " + window.location.pathname.split("/").filter(Boolean).join("/");
    initQiConnection();
  });

</script>

<Window {windowSettings}>
  {@render children()}
</Window>

<style>
  @import url("/styles/root.css");
</style>

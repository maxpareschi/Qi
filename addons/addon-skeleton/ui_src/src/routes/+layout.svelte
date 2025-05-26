<script>
  import { onMount } from "svelte";
  import {
    initQiConnection,
    qiConnection,
  } from "$lib/scripts/qi.windowConnections.svelte";
  import { windowState, windowFlags } from "$lib/scripts/qi.windowState.svelte";
  import Window from "$lib/components/Window/Window.svelte";

  let { children } = $props();

  onMount(() => {
    windowState.title =
      "Qi - " + window.location.pathname.split("/").filter(Boolean).join("/");
    initQiConnection();
  });
</script>

<Window {windowState} {windowFlags}>
  {@render children()}
</Window>

<style>
  @import url("/styles/root.css");
</style>

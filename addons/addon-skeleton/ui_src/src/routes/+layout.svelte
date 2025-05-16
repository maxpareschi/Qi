<script>
  import Window from "$lib/components/Window/Window.svelte";
  import { page } from "$app/stores";
  let { children } = $props();
</script>

<Window>
    {@render children()}
</Window>


<script>
  import QiWindow from "$lib/components/Window/QiWindow.svelte";
  import { page } from "$app/stores";
  import { assets } from "$app/paths";
  let { children } = $props();
</script>

<QiWindow
  title="Window title test"
  status="Status bar test"
  statusExtra="Connected ✔️"
  icon={`${assets}/icons/qi_64.png`}
>
  {@render children()}
</QiWindow>


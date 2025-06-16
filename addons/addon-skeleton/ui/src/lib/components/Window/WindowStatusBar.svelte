<script>
  import { onMount } from "svelte";
  import { windowState } from "$lib/states/qi.windowState.svelte";
  import { qiConnection } from "$lib/scripts/qi.windowConnections.svelte";
  let { showStatusbar, statusMessageMain, statusMessageSub } = $props();

  let socketState = $state(false);

  $effect(() => {
    statusMessageMain = `${qiConnection.session_id} - ${qiConnection.addon}`;
    statusMessageSub = qiConnection.socket?.url || "No connection";
    socketState = qiConnection.connected;
  });
</script>

{#if showStatusbar}
  <div class="statusbar">
    <div class="message-main">{statusMessageMain}</div>
    <div class="message-sub">
      {statusMessageSub}
      {#if socketState}
        <i class="link-icon-success fa-solid fa-link"></i>
      {:else}
        <i class="link-icon-error fa-solid fa-link-slash"></i>
      {/if}
    </div>
  </div>
{/if}

<style>
  .statusbar {
    /*font-family: var(--font-family-monospace);*/
    font-size: var(--font-size-xsmall);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem;
    height: var(--statusbar-height);
    max-height: var(--statusbar-height);
    min-height: var(--statusbar-height);
    background-color: var(--base-color);
    border-top: 1px solid var(--lining-color);
  }
  .link-icon-success {
    color: var(--success-color);
  }
  .link-icon-error {
    color: var(--error-color);
  }
</style>


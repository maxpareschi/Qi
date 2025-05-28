<script>
  import { onMount, onDestroy } from "svelte";
  import { qiConnection } from "$lib/scripts/qi.windowConnections.svelte";

  let windows = $state([]);
  let pingResponse = $state(null);

  // Store unsubscribe functions for cleanup
  let unsubscribeFunctions = [];

  onMount(() => {
    // Subscribe to different message types using the new topic system
    unsubscribeFunctions.push(
      qiConnection.on("wm.window.listed", (envelope) => {
        console.log("Got window list:", envelope.payload.windows);
        windows = envelope.payload.windows || [];
      })
    );

    unsubscribeFunctions.push(
      qiConnection.on("wm.window.opened", (envelope) => {
        console.log("Window opened:", envelope.payload);
        // Refresh the window list
        qiConnection.emit("wm.window.list_all", { payload: {} });
      })
    );

    unsubscribeFunctions.push(
      qiConnection.on("wm.window.closed", (envelope) => {
        console.log("Window closed:", envelope.payload);
        // Refresh the window list
        qiConnection.emit("wm.window.list_all", { payload: {} });
      })
    );

    unsubscribeFunctions.push(
      qiConnection.on("test.pong", (envelope) => {
        console.log("Got ping response:", envelope.payload);
        pingResponse = envelope.payload;
      })
    );
  });

  onDestroy(() => {
    // Clean up subscriptions
    unsubscribeFunctions.forEach((unsub) => unsub());
    unsubscribeFunctions = [];
  });

  const createWindow = () => {
    qiConnection.emit("wm.window.open", { payload: {} });
  };

  const listWindows = () => {
    qiConnection.emit("wm.window.list_all", { payload: {} });
  };

  const closeWindow = (window_id) => {
    qiConnection.emit("wm.window.close", { payload: { window_id } });
  };

  const testPing = () => {
    qiConnection.emit("test.ping", {
      payload: { timestamp: new Date().toISOString() },
    });
  };

  const debugServer = () => {
    qiConnection.emit("debug.server", {
      payload: { timestamp: new Date().toISOString() },
    });
  };
</script>

<button onclick={() => (location.href = "/addon-skeleton")}
  ><i class="fa-solid fa-arrow-left"></i> Back to Home
</button>

<div class="container">
  <h1 style="margin-bottom: 2rem;">Qi Window Manager Demo</h1>

  <div class="info">
    <h3>Connection Info</h3>
    <div class="info-grid">
      <div><strong>Session ID:</strong> {qiConnection.session_id}</div>
      <div
        ><strong>Window ID:</strong>
        {qiConnection.window_id?.slice(0, 8)}...</div
      >
      <div><strong>Addon:</strong> {qiConnection.addon}</div>
      <div
        ><strong>Connected:</strong> {qiConnection.connected ? "✅" : "❌"}</div
      >
    </div>
    <details>
      <summary>Full Context</summary>
      <pre>{JSON.stringify(qiConnection.getConnectionInfo(), null, 2)}</pre>
    </details>
  </div>

  <div class="controls">
    <button class="border" onclick={createWindow}>Create Window</button>
    <button class="border" onclick={listWindows}>List Windows</button>
    <button class="border" onclick={testPing}>Test Ping</button>
    <button class="border" onclick={debugServer}>Debug Server</button>
  </div>

  {#if pingResponse}
    <div class="ping-response">
      <h3>Last Ping Response:</h3>
      <pre>{JSON.stringify(pingResponse, null, 2)}</pre>
    </div>
  {/if}

  <div class="windows-list">
    <h3>Active Windows ({windows.length})</h3>
    {#each windows as window}
      <div class="window-item">
        <span>{window.window_id} - {window.addon}</span>
        <button onclick={() => closeWindow(window.window_id)}>Close</button>
      </div>
    {:else}
      <p
        >No windows found. Click "List Windows" to refresh or "Create Window" to
        add one.</p
      >
    {/each}
  </div>
</div>

<style>
  .container {
    padding: 2rem;
    margin: 0 auto;
  }

  .info,
  .controls,
  .ping-response,
  .windows-list {
    margin-bottom: 2rem;
    padding: 1rem;
    border: 1px solid var(--lining-color);
    border-radius: 0.5rem;
  }

  .info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .info-grid > div {
    padding: 0.5rem;
    background: var(--base-color-light);
    border-radius: 4px;
  }

  .controls {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }

  button {
    padding: 0.5rem 1rem;
    cursor: pointer;
    border-radius: 0.5rem;
  }

  .window-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem;
    margin: 0.5rem 0;
    background: var(--base-color-light);
    border-radius: 4px;
  }

  pre {
    background: var(--base-color-dark);
    padding: 1rem;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.9rem;
  }

  h1,
  h3 {
    color: var(--text-color-hover);
  }
</style>

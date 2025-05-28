<script>
  import { onMount, onDestroy } from "svelte";
  import { qiConnection } from "$lib/scripts/qi.windowConnections.svelte";

  let windows = $state([]);
  let pingResponse = $state(null);
  let errorMessages = $state([]);

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
      qiConnection.on("wm.window.opened", refreshList)
    );

    // Refresh window list when windows are closed or opened
    const refreshList = () => qiConnection.emit("wm.window.list_all", { payload: {} });
    
    unsubscribeFunctions.push(
      qiConnection.on("wm.window.closed", refreshList)
    );
    
    unsubscribeFunctions.push(
      qiConnection.on("wm.window.closed_by_user", refreshList)
    );

    unsubscribeFunctions.push(
      qiConnection.on("test.pong", (envelope) => {
        console.log("Got ping response:", envelope.payload);
        pingResponse = envelope.payload;
      })
    );



    // Error handling - listen for all error topics
    const errorTopics = [
      "wm.window.operation_failed",
      "wm.window.close_failed",
      "wm.window.invoke_failed",
    ];

    errorTopics.forEach((topic) => {
      unsubscribeFunctions.push(
        qiConnection.on(topic, (envelope) => {
          console.error(`❌ ${topic}:`, envelope.payload);
          const errorMsg = {
            timestamp: new Date().toLocaleTimeString(),
            topic,
            error: envelope.payload.error,
            operation: envelope.payload.operation || "unknown",
          };
          errorMessages = [errorMsg, ...errorMessages.slice(0, 9)]; // Keep last 10 errors
        })
      );
    });
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

  const closeWindow = (window_uuid) => {
    qiConnection.emit("wm.window.close", { payload: { window_uuid } });
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

  const minimizeWindow = (window_uuid) => {
    qiConnection.emit("wm.window.minimize", { payload: { window_uuid } });
  };

  const maximizeWindow = (window_uuid) => {
    qiConnection.emit("wm.window.maximize", { payload: { window_uuid } });
  };

  const clearErrors = () => {
    errorMessages = [];
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
      <div><strong>Session:</strong> {qiConnection.session}</div>
      <div>
        <strong>Window UUID:</strong>
        {qiConnection.window_uuid?.slice(0, 8)}...
      </div>
      <div><strong>Addon:</strong> {qiConnection.addon}</div>
      <div>
        <strong>Connected:</strong>
        {qiConnection.connected ? "✅" : "❌"}
      </div>
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

  {#if errorMessages.length > 0}
    <div class="ping-response">
      <div
        style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;"
      >
        <h3>Recent Errors ({errorMessages.length})</h3>
        <button class="border" onclick={clearErrors}>Clear</button>
      </div>
      {#each errorMessages as error}
        <div class="window-item">
          <span>{error.timestamp} - {error.topic} ({error.operation})</span>
          <span style="color: var(--text-color-hover);">{error.error}</span>
        </div>
      {/each}
    </div>
  {/if}

  <div class="windows-list">
    <h3>Active Windows ({windows.length})</h3>
    {#each windows as window}
      <div class="window-item">
        <span>{window.window_uuid.slice(0, 8)}... - {window.addon}</span>
        <div style="display: flex; gap: 0.5rem;">
          <button
            class="border"
            onclick={() => minimizeWindow(window.window_uuid)}>Min</button
          >
          <button
            class="border"
            onclick={() => maximizeWindow(window.window_uuid)}>Max</button
          >
          <button class="border" onclick={() => closeWindow(window.window_uuid)}
            >Close</button
          >
        </div>
      </div>
    {:else}
      <p>
        No windows found. Click "List Windows" to refresh or "Create Window" to
        add one.
      </p>
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

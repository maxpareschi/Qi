<script>
  import { qiSocket, qiSend } from "$lib/helpers/qi.connection.svelte";
  
  let windows = $state([]);
  let pingResponse = $state(null);
  
  qiSocket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log("Received message from server: ", data);
    
    // Handle different message types
    if (data.topic === "wm.window.listed") {
      console.log("Got window list:", data.payload.windows);
      windows = data.payload.windows || [];
    } 
    else if (data.topic === "wm.window.opened") {
      console.log("Window opened:", data.payload);
      // Refresh the window list
      qiSend("wm.window.list_all", {});
    }
    else if (data.topic === "wm.window.closed") {
      console.log("Window closed:", data.payload);
      // Refresh the window list
      qiSend("wm.window.list_all", {});
    }
    else if (data.topic === "test.pong") {
      console.log("Got ping response:", data.payload);
      pingResponse = data.payload;
    }
  };

  const createWindow = () => {
    qiSend("wm.window.open", { addon: "addon-skeleton" });
  };
  const listWindows = () => {
    qiSend("wm.window.list_all", {});
  };

  const closeWindow = (window_uuid) => {
    qiSend("wm.window.close", { window_uuid });
  };
  
  const testPing = () => {
    qiSend("test.ping", { timestamp: new Date().toISOString() });
  };
  
  const debugServer = () => {
    qiSend("debug.server", { timestamp: new Date().toISOString() });
  };
</script>

<div class="container">
  <button onclick={() => (location.href = "/addon-skeleton")}>
    <i class="fa-solid fa-arrow-left"></i>
    Back to home
  </button>
  <h3>Demo addon-skeleton</h3>
  <div class="buttons">
    <button class="border" onclick={createWindow}>Create window</button>
    <button class="border" onclick={listWindows}>List windows</button>
    <button class="border" onclick={testPing}>Test Ping</button>
    <button class="border" onclick={debugServer}>Debug Server</button>
  </div>

  {#if pingResponse}
    <div class="ping-response">
      <p>Ping response: {JSON.stringify(pingResponse)}</p>
    </div>
  {/if}

  <ul>
    {#each windows as window}
      <li>
        <p>{window.window_uuid} - {window.addon}</p>
        <button class="button-icon" onclick={() => closeWindow(window.window_uuid)}>
          <i class="fa-solid fa-circle-xmark"></i>
          Close
        </button>
      </li>
    {/each}
  </ul>
</div>

<style>
  ul {
    list-style: none;
    padding: 2rem;
  }

  li {
    display: flex;
    justify-content: flex-start;
    align-items: center;
  }

  .container {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-start;
    gap: 2rem;
  }

  .buttons {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    gap: 1rem;
  }
  
  .ping-response {
    background-color: #f0f0f0;
    padding: 1rem;
    border-radius: 0.5rem;
  }
</style>

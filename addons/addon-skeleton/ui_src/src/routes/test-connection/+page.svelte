<script>
  import { onMount, onDestroy } from "svelte";
  import { qiConnection } from "$lib/scripts/qi.windowConnections.svelte";
  
  let messages = $state([]);
  let testInput = $state("");
  let unsubscribeFunctions = [];
  
  onMount(() => {
    // Subscribe to all test messages
    unsubscribeFunctions.push(
      qiConnection.on("test.echo.reply", (envelope) => {
        messages.push({
          type: "echo_reply",
          topic: envelope.topic,
          payload: envelope.payload,
          timestamp: new Date().toISOString(),
          envelope
        });
        messages = [...messages]; // trigger reactivity
      })
    );
    
    unsubscribeFunctions.push(
      qiConnection.on("test.pong", (envelope) => {
        messages.push({
          type: "pong",
          topic: envelope.topic,
          payload: envelope.payload,
          timestamp: new Date().toISOString(),
          envelope
        });
        messages = [...messages]; // trigger reactivity
      })
    );
  });
  
  onDestroy(() => {
    unsubscribeFunctions.forEach(unsub => unsub());
  });
  
  const sendTestMessage = () => {
    if (!testInput.trim()) return;
    
    const payload = { message: testInput, timestamp: new Date().toISOString() };
    qiConnection.emit("test.echo", {payload});
    
    messages.push({
      type: "sent",
      topic: "test.echo", 
      payload,
      timestamp: new Date().toISOString()
    });
    messages = [...messages]; // trigger reactivity
    
    testInput = "";
  };
  
  const sendPing = () => {
    qiConnection.emit("test.ping", {payload: { timestamp: new Date().toISOString() }});
    
    messages.push({
      type: "sent", 
      topic: "test.ping",
      payload: { timestamp: new Date().toISOString() },
      timestamp: new Date().toISOString()
    });
    messages = [...messages]; // trigger reactivity
  };
  
  const clearMessages = () => {
    messages = [];
  };
</script>

<button onclick={() => (location.href = "/addon-skeleton")}
  ><i class="fa-solid fa-arrow-left"></i> Back to Home
</button>

<div class="border container">
  <h1>🧪 Connection Test Lab</h1>
  
  <div class="border status">
    <h3>Connection Status</h3>
    <div class="status-grid">
      <div>
        <strong>Connected:</strong> {qiConnection.connected ? "✅ Yes" : "❌ No"}
      </div>
      <div>
        <strong>Session:</strong> {qiConnection.session}
      </div>
      <div>
        <strong>Addon:</strong> {qiConnection.addon}
      </div>
      <div>
        <strong>URL:</strong> {qiConnection.socket?.url || "Not connected"}
      </div>
    </div>
  </div>
  
  <div class="border context">
    <h3>Context</h3>
    <pre>{JSON.stringify(qiConnection.context, null, 2)}</pre>
  </div>
  
  <div class="border test-controls">
    <h3>Test Controls</h3>
    <div class="input-group">
      <input
        bind:value={testInput} 
        placeholder="Enter test message..."
        onkeydown={(e) => e.key === "Enter" && sendTestMessage()}
      />
      <button class="border" onclick={sendTestMessage} disabled={!testInput.trim()}>
        Send Echo
      </button>
    </div>
    <div>
      <button class="border" onclick={sendPing}>Send Ping</button>
      <button class="border" onclick={clearMessages}>Clear Messages</button>
    </div>
  </div>
  
  <div class="border messages">
    <h3>Messages ({messages.length})</h3>
    <div class="messages-list">
      {#each messages.slice().reverse() as message}
        <div class="message message-{message.type}">
          <div class="message-header">
            <span class="message-type">{message.type.toUpperCase()}</span>
            <span class="message-topic">{message.topic}</span>
            <span class="message-time">{new Date(message.timestamp).toLocaleTimeString()}</span>
          </div>
          <div class="message-payload">
            <pre>{JSON.stringify(message.payload, null, 2)}</pre>
          </div>
        </div>
      {:else}
        <p class="no-messages">No messages yet. Try sending a test message!</p>
      {/each}
    </div>
  </div>
</div>

<style>
  .container {
    padding: 2rem;
    margin: 2rem;
    border-radius: 0.5rem;
  }

  .status, .context, .test-controls, .messages {
    margin: 1rem;
    padding: 1rem;
    border-radius: 8px;
  }

  .status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
  }

  .status-grid > * {
    padding: 0.5rem;
    border-radius: 0.5rem;
    border: 1px solid var(--lining-color);
    background: var(--bg-color-lighter);
  }

  .input-group {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  
  .input-group input {
    flex: 1;
    padding: 0.5rem;
    border-radius: 0.5rem;
    border: 1px solid var(--lining-color);
    color: var(--text-color-hover);
    background: var(--base-color-darker);
  }
  
  .message {
    margin-bottom: 1rem;
    padding: 1rem;
    border-radius: 0.5rem;
    background-color: var(--bg-color-darker);
    border-left: 0.25rem solid var(--accent-color);
  }

  .message-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
  }
  
  .message-type {
    font-weight: bold;
    text-transform: uppercase;
  }
  
  .message-topic {
    font-family: monospace;
    padding: 0.2rem 0.4rem;
    border-radius: 0.2rem;
  }
  
  .message-time {
    opacity: 0.7;
    font-size: 0.8rem;
  }
  
  .message-payload pre {
    margin: 0;
    font-size: 0.85rem;
    padding: 0.5rem;
    border-radius: 0.2rem;
    overflow-x: auto;
  }
  
  .no-messages {
    text-align: center;
    opacity: 0.7;
    font-style: italic;
  }
  
  button {
    padding: 0.5rem 1rem;
    cursor: pointer;
    border-radius: 0.5rem;
    &:disabled {
      border: 1px solid transparent;
      cursor: not-allowed;
      color: var(--text-color);
      background-color: var(--base-color-darker);
    }
  }

  pre {
    font-size: 0.9rem;
    padding: 1rem;
    border-radius: 0.5rem;
  }
  
  h1, h3 {
    margin-top: 0;
    margin-bottom: 1rem;
    color: var(--text-color-hover);
  }
</style> 
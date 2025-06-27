<script>
  import { assets } from "$app/paths";
</script>

<button onclick={() => (location.href = "/extension-skeleton/demo")}
  >Go to Demo Page
  <i class="fa-solid fa-arrow-right"></i>
</button>
<button onclick={() => (location.href = "/extension-skeleton/test-connection")}
  >Go to Test Connection Page
  <i class="fa-solid fa-arrow-right"></i>
</button>

<div class="container">
  <h1>Welcome to the Extensions Skeleton Test UI</h1>
  <img src="{assets}/icons/qi_512.png" alt="Logo" />
  <p>
    This is a test UI for the Extensions Skeleton. It is used to test the Extensions
    Skeleton.
  </p>
</div>

<style>
  .container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--lining-color);
    border-radius: 0.5rem;
    padding: 2rem;
    margin: 2rem;
    gap: 2rem;
  }
  .container img {
    width: 7rem;
    height: 7rem;
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

  h1, h3 {
    margin-top: 0;
    margin-bottom: 1rem;
    color: var(--text-color-hover);
  }
</style>

<script>
  import { assets } from "$app/paths";
</script>

<div class="container">
  <img src="{assets}/icons/qi_512.png" alt="Logo" />
  <h1>WELCOME TO ADDONS SKELETON TEST UI</h1>
</div>

<button onclick={() => (location.href = "/addon-skeleton/demo")}
  >Go to Demo Page
  <i class="fa-solid fa-arrow-right"></i>
</button>

<style>
  .container {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    gap: 2rem;
    margin-bottom: 2rem;
  }
  .container img {
    width: 10rem;
    height: 10rem;
  }
</style>

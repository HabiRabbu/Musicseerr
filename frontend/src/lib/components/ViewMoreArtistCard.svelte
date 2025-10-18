<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { colors } from '$lib/colors';

  let imgError = false;
  
  function handleError() {
    console.error('Failed to load artist_bg.png');
    imgError = true;
  }

  function handleClick() {
    const query = $page.url.searchParams.get('q') || '';
    if (query) {
      goto(`/search/artists?q=${encodeURIComponent(query)}`);
    }
  }
</script>

<button class="relative w-full aspect-square cursor-pointer transition-transform duration-200 ease-in-out hover:scale-105" on:click={handleClick}>
  <div class="stack w-full h-full">
    {#if imgError}
      <div class="bg-base-200 shadow-sm w-full h-full rounded-box"></div>
      <div class="bg-base-200 shadow w-full h-full rounded-box"></div>
      <div class="bg-base-100 shadow-md w-full h-full rounded-box"></div>
    {:else}
      <div class="bg-base-100 shadow-sm w-full h-full rounded-box overflow-hidden">
        <img src="/img/artist_bg.png?v=2" alt="" class="w-full h-full object-cover" style="filter: blur(8px);" on:error={handleError} />
      </div>
      <div class="bg-base-100 shadow w-full h-full rounded-box overflow-hidden">
        <img src="/img/artist_bg.png?v=2" alt="" class="w-full h-full object-cover" style="filter: blur(8px);" on:error={handleError} />
      </div>
      <div class="bg-base-100 shadow-md w-full h-full rounded-box overflow-hidden">
        <img src="/img/artist_bg.png?v=2" alt="" class="w-full h-full object-cover" style="filter: blur(8px);" on:error={handleError} />
      </div>
    {/if}
  </div>
  <div class="absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none">
    <div class="px-6 py-4 rounded-lg backdrop-blur-sm" style="background-color: {colors.secondary}66;">
      <span class="text-sm font-semibold mb-1 block text-center drop-shadow-lg" style="color: {colors.accent};">View More</span>
      <span class="text-3xl font-bold block text-center drop-shadow-lg" style="color: {colors.accent};">ARTISTS</span>
    </div>
  </div>
</button>

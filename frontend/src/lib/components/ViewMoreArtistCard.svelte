<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { colors } from '$lib/colors';

  let imgError = false;
  
  function handleError() {
    imgError = true;
  }

  function handleClick() {
    const query = $page.url.searchParams.get('q') || '';
    if (query) {
      goto(`/search/artists?q=${encodeURIComponent(query)}`);
    }
  }
</script>

<button class="relative w-full aspect-square cursor-pointer transition-transform duration-200 ease-in-out hover:scale-105 rounded-full overflow-hidden" on:click={handleClick}>
  {#if imgError}
    <div class="absolute inset-0 bg-base-200"></div>
  {:else}
    <div class="absolute inset-0 overflow-hidden">
      <img src="/img/artist_bg.png?v=2" alt="" class="w-full h-full object-cover" style="filter: blur(8px);" on:error={handleError} />
    </div>
  {/if}
  <div class="absolute inset-0 z-10 flex flex-col items-center justify-center p-2">
    <div class="px-2 py-1 rounded-lg backdrop-blur-sm shadow-lg max-w-full" style="background-color: {colors.secondary}66;">
      <div class="flex flex-col items-center gap-0.5">
        <span class="text-sm font-bold block text-center drop-shadow-lg truncate" style="color: {colors.accent};">ARTISTS</span>
        <div class="flex items-center gap-1">
          <span class="text-xs font-semibold text-center drop-shadow-lg" style="color: {colors.accent};">View More</span>
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 drop-shadow-lg" fill="none" viewBox="0 0 24 24" stroke={colors.accent} stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </div>
  </div>
</button>

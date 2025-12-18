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

<button class="relative w-full aspect-square cursor-pointer transition-transform duration-200 ease-in-out hover:scale-105 rounded-box" on:click={handleClick}>
  {#if imgError}
    <div class="absolute inset-0 bg-base-200 rounded-box"></div>
  {:else}
    <div class="absolute inset-0 rounded-box overflow-hidden">
      <img src="/img/artist_bg.png?v=2" alt="" class="w-full h-full object-cover" style="filter: blur(8px);" on:error={handleError} />
    </div>
  {/if}
  <div class="absolute inset-0 z-10 flex flex-col items-center justify-center">
    <div class="px-3 py-2 sm:px-6 sm:py-4 rounded-lg backdrop-blur-sm shadow-lg" style="background-color: {colors.secondary}66;">
      <div class="flex flex-col items-center gap-1 sm:gap-2">
        <span class="text-lg sm:text-3xl font-bold block text-center drop-shadow-lg" style="color: {colors.accent};">ARTISTS</span>
        <div class="flex items-center gap-1 sm:gap-2">
          <span class="text-xs sm:text-sm font-semibold text-center drop-shadow-lg" style="color: {colors.accent};">View More</span>
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 sm:h-4 sm:w-4 drop-shadow-lg" fill="none" viewBox="0 0 24 24" stroke={colors.accent} stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </div>
  </div>
</button>

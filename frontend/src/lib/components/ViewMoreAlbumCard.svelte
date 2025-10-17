<script lang="ts">
  let imgError = false;
  
  function handleError() {
    console.error('Failed to load album_bg.png');
    imgError = true;
  }
</script>

<div class="relative w-full aspect-square">
  <div class="stack w-full h-full">
    {#if imgError}
      <div class="bg-base-200 shadow-sm w-full h-full rounded-box"></div>
      <div class="bg-base-200 shadow w-full h-full rounded-box"></div>
      <div class="bg-base-100 shadow-md w-full h-full rounded-box"></div>
    {:else}
      <div class="bg-base-100 shadow-sm w-full h-full rounded-box overflow-hidden">
        <img src="/img/album_bg.png?v=2" alt="" class="w-full h-full object-cover" style="filter: blur(8px);" on:error={handleError} />
      </div>
      <div class="bg-base-100 shadow w-full h-full rounded-box overflow-hidden">
        <img src="/img/album_bg.png?v=2" alt="" class="w-full h-full object-cover" style="filter: blur(8px);" on:error={handleError} />
      </div>
      <div class="bg-base-100 shadow-md w-full h-full rounded-box overflow-hidden">
        <img src="/img/album_bg.png?v=2" alt="" class="w-full h-full object-cover" style="filter: blur(8px);" on:error={handleError} />
      </div>
    {/if}
  </div>
  <div class="absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none">
    <div class="px-6 py-4 rounded-lg backdrop-blur-sm" style="background-color: rgba(29, 35, 42, 0.4);">
      <span class="text-sm font-semibold mb-1 block text-center drop-shadow-lg" style="color: #CAFF8A;">View More</span>
      <span class="text-3xl font-bold block text-center drop-shadow-lg" style="color: #CAFF8A;">ALBUMS</span>
    </div>
  </div>
</div>

<script lang="ts">
  import type { Album } from '$lib/types';
  import { colors } from '$lib/colors';

  export let album: Album;
  export let index: number = 0;
  export let onadded: (() => void) | undefined = undefined;
  
  let requesting = false;
  let inLibrary = album.in_library;
  let coverUrl = album.cover_url ?? `/api/covers/release-group/${album.musicbrainz_id}?size=250`;
  let imgError = false;
  let imgLoaded = false;

  function onImgError() {
    imgError = true;
  }

  function onImgLoad(e: Event) {
    imgLoaded = true;
    (e.currentTarget as HTMLImageElement).classList.remove('opacity-0');
  }

  $: coverUrl = album.cover_url ?? `/api/covers/release-group/${album.musicbrainz_id}?size=250`;

  async function handleRequest() {
    requesting = true;
    try {
      await fetch('/api/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ musicbrainz_id: album.musicbrainz_id })
      });
      inLibrary = true;
      onadded?.();
    } catch (error) {
      console.error('Failed to request album:', error);
    } finally {
      requesting = false;
    }
  }

  $: displayYear = album.year ?? 'Unknown';

</script>

<div class="card bg-base-100 w-full shadow-sm flex-shrink-0 group relative">
  <figure class="aspect-square overflow-hidden relative">
    {#if imgError}
      <div class="w-full h-full flex items-center justify-center text-6xl opacity-50 bg-base-200">
        💿
      </div>
    {:else}
      {#if !imgLoaded}
        <div class="skeleton w-full h-full absolute inset-0"></div>
      {/if}
      <img
        src={coverUrl}
        alt={album.title}
        class="w-full h-full object-cover opacity-0 transition-opacity duration-300"
        loading="lazy"
        decoding="async"
        fetchpriority={index < 6 ? 'high' : 'auto'}
        on:error={onImgError}
        on:load={onImgLoad}
      />
    {/if}
  </figure>

  <!-- In Library Checkmark -->
  {#if inLibrary}
    <div class="absolute top-2 right-2 rounded-full p-1.5 shadow-lg" style="background-color: {colors.accent};">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
        <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    </div>
  {/if}

  <div class="card-body p-3">
    <h2 class="card-title text-sm line-clamp-2 min-h-[2.5rem]">{album.title}</h2>
    <p class="text-xs opacity-70 line-clamp-1">
      {#if album.year}{album.year}{:else}Unknown{/if}
      {#if album.artist}
        <span class="opacity-50 mx-1">•</span>
        {album.artist}
      {/if}
    </p>
  </div>

  <!-- Hover-only Request Button -->
  {#if !inLibrary}
    <button
      class="absolute bottom-2 right-2 btn btn-square btn-md opacity-0 group-hover:opacity-100 transition-opacity duration-200 border-none shadow-lg"
      style="background-color: {colors.accent};"
      on:click={handleRequest}
      disabled={requesting}
      aria-label="Request album"
    >
      {#if requesting}
        <span class="loading loading-spinner loading-sm" style="color: {colors.secondary};"></span>
      {:else}
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
      {/if}
    </button>
  {/if}
</div>

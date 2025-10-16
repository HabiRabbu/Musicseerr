<script lang="ts">
  import type { Album } from '$lib/types';

  export let album: Album;
  export let index: number = 0;  // Position in grid for fetchpriority
  
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
    await fetch('/api/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ musicbrainz_id: album.musicbrainz_id })
    });
    requesting = false;
    inLibrary = true;
  }
</script>

<div class="card bg-base-100 w-full shadow-sm flex-shrink-0">
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

  <div class="card-body p-3">
    <h2 class="card-title text-sm line-clamp-2 min-h-[2.5rem]">{album.title}</h2>
    <p class="text-xs opacity-70 line-clamp-1">{album.artist}</p>
    <div class="card-actions justify-end mt-2">
      <button
        class="btn btn-primary btn-sm w-full"
        class:btn-success={inLibrary}
        on:click={handleRequest}
        disabled={requesting || inLibrary}
      >
        {#if requesting}
          <span class="loading loading-spinner loading-xs"></span>
        {:else if inLibrary}
          In Library
        {:else}
          Request
        {/if}
      </button>
    </div>
  </div>
</div>

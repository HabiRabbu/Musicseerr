<script lang="ts">
	import { Check } from 'lucide-svelte';
	import type { ArtistInfo } from '$lib/types';
	import { extractDominantColor, DEFAULT_GRADIENT } from '$lib/utils/colors';
	import ArtistLinks from './ArtistLinks.svelte';
	import BackButton from './BackButton.svelte';

	export let artist: ArtistInfo;
	export let showBackButton: boolean = false;

	let heroGradient = DEFAULT_GRADIENT;
	let heroImageLoaded = false;
	let fanartLoaded = false;
	let fanartError = false;
	let coverBgLoaded = false;

	function onHeroImageLoad() {
		heroImageLoaded = true;
		if (!artist.fanart_url || fanartError) {
			extractDominantColor(`/api/covers/artist/${artist.musicbrainz_id}?size=250`).then(
				(gradient) => (heroGradient = gradient)
			);
		}
	}

	$: if (fanartError && artist && heroImageLoaded) {
		extractDominantColor(`/api/covers/artist/${artist.musicbrainz_id}?size=250`).then(
			(gradient) => (heroGradient = gradient)
		);
	}

	$: useCoverBg = heroImageLoaded && (!artist.fanart_url || fanartError);
	$: coverBgUrl = `/api/covers/artist/${artist.musicbrainz_id}?size=500`;

	$: validLinks = artist.external_links.filter((link) => link.url && link.url.trim() !== '');
</script>

<div class="relative -mx-2 sm:-mx-4 lg:-mx-8 -mt-4 sm:-mt-8 overflow-hidden bg-gradient-to-b from-primary/15 via-primary/5 to-transparent">
	{#if artist.fanart_url && !fanartError}
		<div class="absolute inset-0">
			<img
				src={artist.fanart_url}
				alt=""
				class="w-full h-full object-cover transition-opacity duration-700 {fanartLoaded
					? 'opacity-30'
					: 'opacity-0'}"
				loading="eager"
				on:load={() => (fanartLoaded = true)}
				on:error={() => (fanartError = true)}
			/>
			<div class="absolute inset-0 bg-gradient-to-b from-transparent via-base-100/60 to-base-100"
			></div>
		</div>
	{:else}
		<div class="absolute inset-0 bg-gradient-to-b {heroGradient} transition-all duration-1000"
		></div>
		{#if useCoverBg}
			<div class="absolute inset-0 overflow-hidden">
				<img
					src={coverBgUrl}
					alt=""
					class="w-full h-full object-cover scale-110 blur-xl transition-opacity duration-700 {coverBgLoaded
						? 'opacity-25'
						: 'opacity-0'}"
					loading="eager"
					on:load={() => (coverBgLoaded = true)}
				/>
				<div class="absolute inset-0 bg-gradient-to-b from-transparent via-base-100/60 to-base-100"
				></div>
			</div>
		{/if}
	{/if}

	<div class="relative z-10 px-4 sm:px-8 lg:px-12 pt-6 pb-8 sm:pt-8 sm:pb-12">
		<div class="max-w-7xl mx-auto">
			{#if showBackButton}
				<div class="mb-4">
					<BackButton />
				</div>
			{/if}
			<div class="flex flex-col sm:flex-row items-center sm:items-end gap-6 sm:gap-8">
				<div class="flex-shrink-0">
					<div class="relative">
						<div
							class="w-40 h-40 sm:w-52 sm:h-52 lg:w-64 lg:h-64 rounded-full overflow-hidden shadow-2xl ring-4 ring-base-100/20"
							style="background-color: #0d120a;"
						>
							{#if !heroImageLoaded}
								<div class="absolute inset-0 flex items-center justify-center">
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 200 200"
										class="w-full h-full"
									>
										<rect fill="#0d120a" width="200" height="200" />
										<circle cx="100" cy="80" r="30" fill="#1F271B" />
										<path
											d="M60 120 Q100 140 140 120 L140 160 Q100 180 60 160 Z"
											fill="#1F271B"
										/>
									</svg>
								</div>
							{/if}
							<img
								src="/api/covers/artist/{artist.musicbrainz_id}?size=500"
								alt={artist.name}
								class="w-full h-full object-cover transition-opacity duration-300 {heroImageLoaded
									? 'opacity-100'
									: 'opacity-0'}"
								loading="lazy"
								decoding="async"
								on:load={onHeroImageLoad}
								on:error={(e) => {
									const target = e.currentTarget as HTMLImageElement;
									target.style.display = 'none';
								}}
							/>
						</div>
						{#if artist.in_library}
							<div class="absolute -bottom-2 -right-2 badge badge-success badge-lg gap-1 shadow-lg">
							<Check class="h-4 w-4" />
								In Library
							</div>
						{/if}
					</div>
				</div>

				<div class="flex-1 text-center sm:text-left min-w-0">
					{#if artist.type}
						<span class="text-xs sm:text-sm font-medium text-base-content/70 uppercase tracking-wider">
							{artist.type === 'Group' ? 'Band' : artist.type === 'Person' ? 'Artist' : artist.type}
						</span>
					{/if}
					<h1
						class="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-bold text-base-content mt-1 mb-2 break-words"
					>
						{artist.name}
					</h1>
					{#if artist.disambiguation}
						<p class="text-base-content/60 text-sm sm:text-base mb-3">({artist.disambiguation})</p>
					{/if}

					{#if validLinks.length > 0}
						<ArtistLinks links={validLinks} />
					{/if}
				</div>
			</div>
		</div>
	</div>
</div>

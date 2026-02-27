<script lang="ts">
	export let title: string;
	export let genres: { name: string }[];
	export let genreArtists: Record<string, string | null> | undefined = undefined;

	const genreColors = [
		'from-rose-500 to-pink-600',
		'from-violet-500 to-purple-600',
		'from-blue-500 to-cyan-600',
		'from-emerald-500 to-teal-600',
		'from-amber-500 to-orange-600',
		'from-red-500 to-rose-600',
		'from-indigo-500 to-violet-600',
		'from-cyan-500 to-blue-600',
		'from-green-500 to-emerald-600',
		'from-orange-500 to-amber-600'
	];

	function getGenreColor(name: string): string {
		return genreColors[name.length % genreColors.length];
	}
</script>

<section>
	<div class="mb-4 flex items-center justify-between">
		<h2 class="text-lg font-bold sm:text-xl">{title}</h2>
	</div>
	<div class="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 md:grid-cols-4 lg:grid-cols-5">
		{#each genres.slice(0, 20) as genre}
			{@const artistMbid = genreArtists?.[genre.name]}
			<a
				href="/genre?name={encodeURIComponent(genre.name)}"
				class="card relative overflow-hidden text-white shadow-lg transition-all duration-200 hover:scale-105 hover:shadow-xl active:scale-95"
			>
				<div class="absolute inset-0 bg-gradient-to-br {getGenreColor(genre.name)}"></div>
				{#if artistMbid}
					<img
						src="/api/covers/artist/{artistMbid}?size=250"
						alt=""
						class="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-25"
						style="z-index: 5;"
						loading="lazy"
					/>
				{/if}
				<div
					class="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent"
					style="z-index: 6;"
				></div>
				<div
					class="card-body relative min-h-24 justify-end p-3 sm:min-h-28 sm:p-4"
					style="z-index: 10;"
				>
					<h3 class="text-xs font-bold drop-shadow-lg sm:text-sm">{genre.name}</h3>
				</div>
			</a>
		{/each}
	</div>
</section>

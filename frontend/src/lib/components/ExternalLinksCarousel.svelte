<script lang="ts">
	interface ExternalLink {
		label: string;
		url: string;
	}

	export let links: ExternalLink[];

	let carouselElement: HTMLDivElement;

	const linkIcons: Record<string, string> = {
		'Spotify': '🎵',
		'YouTube': '▶️',
		'Instagram': '📷',
		'Twitter': '🐦',
		'Facebook': '👥',
		'Bandcamp': '🎹',
		'SoundCloud': '☁️',
		'Official Website': '🌐',
		'Wikipedia': '📖',
		'Discogs': '💿',
		'AllMusic': '🎼',
		'Last.fm': '📻',
		'Apple Music': '🍎',
		'Deezer': '🎧'
	};

	function getIcon(label: string): string {
		return linkIcons[label] || '🔗';
	}

	function scroll(direction: 'left' | 'right') {
		if (carouselElement) {
			const scrollAmount = 400;
			const newPosition =
				carouselElement.scrollLeft + (direction === 'right' ? scrollAmount : -scrollAmount);
			carouselElement.scrollTo({
				left: newPosition,
				behavior: 'smooth'
			});
		}
	}
</script>

<style>
	.scrollbar-hide {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}
	.scrollbar-hide::-webkit-scrollbar {
		display: none;
	}
</style>

<div>
	<h2 class="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Links</h2>
	<div class="relative">
		<button
			class="btn btn-circle btn-sm absolute left-0 top-1/2 -translate-y-1/2 z-10 bg-base-300 border-none shadow-lg hidden sm:flex"
			on:click={() => scroll('left')}
			aria-label="Scroll left"
		>
			❮
		</button>

		<div class="overflow-x-auto scrollbar-hide sm:px-12" bind:this={carouselElement}>
			<div class="flex gap-3 sm:gap-4 p-3 sm:p-4 bg-base-200 rounded-box shadow-md w-max">
				{#each links as link}
					<a
						href={link.url}
						target="_blank"
						rel="noopener noreferrer"
						class="card card-compact bg-base-100 hover:bg-base-300 shadow-sm hover:shadow-md transition-all w-32 h-20 sm:w-40 sm:h-24 flex-shrink-0"
					>
						<div class="card-body items-center justify-center text-center p-2">
							<div class="text-xl sm:text-2xl mb-0.5 sm:mb-1">
								{getIcon(link.label)}
							</div>
							<h3 class="text-xs sm:text-sm font-semibold line-clamp-2">{link.label}</h3>
						</div>
					</a>
				{/each}
			</div>
		</div>

		<button
			class="btn btn-circle btn-sm absolute right-0 top-1/2 -translate-y-1/2 z-10 bg-base-300 border-none shadow-lg hidden sm:flex"
			on:click={() => scroll('right')}
			aria-label="Scroll right"
		>
			❯
		</button>
	</div>
</div>

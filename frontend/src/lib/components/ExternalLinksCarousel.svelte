<script lang="ts">
	import HorizontalCarousel from './HorizontalCarousel.svelte';

	interface ExternalLink {
		label: string;
		url: string;
	}

	interface Props {
		links: ExternalLink[];
	}

	let { links }: Props = $props();

	const linkIcons: Record<string, string> = {
		Spotify: '🎵',
		YouTube: '▶️',
		Instagram: '📷',
		Twitter: '🐦',
		Facebook: '👥',
		Bandcamp: '🎹',
		SoundCloud: '☁️',
		'Official Website': '🌐',
		Wikipedia: '📖',
		Discogs: '💿',
		AllMusic: '🎼',
		'Last.fm': '📻',
		'Apple Music': '🍎',
		Deezer: '🎧'
	};

	function getIcon(label: string): string {
		return linkIcons[label] || '🔗';
	}
</script>

<div>
	<h2 class="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Links</h2>
	<HorizontalCarousel>
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
	</HorizontalCarousel>
</div>

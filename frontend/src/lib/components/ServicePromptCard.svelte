<script lang="ts">
	import type { ServicePrompt } from '$lib/types';

	export let prompt: ServicePrompt;

	function getPromptGradient(color: string): string {
		switch (color) {
			case 'primary':
				return 'from-primary/20 to-primary/5 border-primary/30';
			case 'secondary':
				return 'from-secondary/20 to-secondary/5 border-secondary/30';
			case 'accent':
				return 'from-accent/20 to-accent/5 border-accent/30';
			default:
				return 'from-base-200 to-base-100 border-base-300';
		}
	}

	function getPromptButtonClass(color: string): string {
		switch (color) {
			case 'primary':
				return 'btn-primary';
			case 'secondary':
				return 'btn-secondary';
			case 'accent':
				return 'btn-accent';
			default:
				return 'btn-neutral';
		}
	}

	function getSettingsLink(service: string): string {
		return `/settings?tab=${service}`;
	}
</script>

<div
	class="card overflow-hidden border bg-gradient-to-r shadow-lg {getPromptGradient(prompt.color)}"
>
	<div class="card-body flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:p-6">
		<div class="flex-shrink-0 text-4xl sm:text-5xl">{prompt.icon}</div>
		<div class="min-w-0 flex-1">
			<h3 class="card-title mb-1 text-base sm:text-lg">{prompt.title}</h3>
			<p class="mb-2 text-xs text-base-content/70 sm:mb-3 sm:text-sm">
				{prompt.description}
			</p>
			<div class="flex flex-wrap gap-1 sm:gap-2">
				{#each prompt.features as feature}
					<span class="badge badge-ghost badge-xs sm:badge-sm">{feature}</span>
				{/each}
			</div>
		</div>
		<div class="flex-shrink-0">
			<a href={getSettingsLink(prompt.service)} class="btn btn-sm sm:btn-md {getPromptButtonClass(prompt.color)}">
				Connect
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
					<path
						fill-rule="evenodd"
						d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z"
						clip-rule="evenodd"
					/>
				</svg>
			</a>
		</div>
	</div>
</div>

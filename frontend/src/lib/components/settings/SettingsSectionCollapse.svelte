<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { SvelteComponent } from 'svelte';

	let {
		title,
		description,
		icon: Icon,
		iconBgClass = 'bg-primary/10',
		iconTextClass = 'text-primary',
		sectionId,
		isOpen = $bindable(false),
		name = 'advanced-settings',
		children
	}: {
		title: string;
		description: string;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		icon: typeof SvelteComponent<any>;
		iconBgClass?: string;
		iconTextClass?: string;
		sectionId: string;
		isOpen?: boolean;
		name?: string;
		children: Snippet;
	} = $props();
</script>

<div class="collapse collapse-arrow bg-base-200 rounded-box">
	<input type="radio" {name} checked={isOpen} onchange={() => (isOpen = true)} />
	<div class="collapse-title">
		<div class="flex items-center gap-3">
			<div class="{iconBgClass} p-2 rounded-lg">
				<Icon class="w-5 h-5 {iconTextClass}" />
			</div>
			<div>
				<h3 class="font-semibold text-base">{title}</h3>
				<p class="text-xs text-base-content/50">{description}</p>
			</div>
		</div>
	</div>
	<div class="collapse-content">
		{@render children()}
	</div>
</div>

<script lang="ts">
	interface Props {
		current: number;
		total: number;
		onchange: (page: number) => void;
	}

	let { current, total, onchange }: Props = $props();
</script>

{#if total > 1}
	<div class="flex items-center gap-2">
		<button
			class="btn btn-sm btn-circle"
			onclick={() => onchange(Math.max(1, current - 1))}
			disabled={current === 1}
			aria-label="Previous page"
		>
			«
		</button>
		<span class="text-sm">{current} / {total}</span>
		<button
			class="btn btn-sm btn-circle"
			onclick={() => onchange(Math.min(total, current + 1))}
			disabled={current === total}
			aria-label="Next page"
		>
			»
		</button>
	</div>
{/if}

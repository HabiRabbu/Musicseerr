<script lang="ts">
	import { Check, X, Info, TriangleAlert } from 'lucide-svelte';
	import { TOAST_DURATION } from '$lib/constants';

	interface Props {
		show?: boolean;
		message?: string;
		type?: 'success' | 'error' | 'info' | 'warning';
		duration?: number;
	}

	let {
		show = $bindable(false),
		message = 'Added to Library',
		type = 'success',
		duration = TOAST_DURATION
	}: Props = $props();

	$effect(() => {
		if (show && duration > 0) {
			const timeout = setTimeout(() => {
				show = false;
			}, duration);
			return () => clearTimeout(timeout);
		}
	});

	const alertClasses: Record<string, string> = {
		success: 'alert-success',
		error: 'alert-error',
		info: 'alert-info',
		warning: 'alert-warning'
	};
</script>

{#if show}
	<div class="toast toast-end toast-bottom">
		<div class="alert {alertClasses[type]}">
			{#if type === 'success'}
				<Check class="h-6 w-6" strokeWidth={2} />
			{:else if type === 'error'}
				<X class="h-6 w-6" strokeWidth={2} />
			{:else if type === 'info'}
				<Info class="h-6 w-6" strokeWidth={2} />
			{:else if type === 'warning'}
				<TriangleAlert class="h-6 w-6" strokeWidth={2} />
			{/if}
			<span>{message}</span>
		</div>
	</div>
{/if}

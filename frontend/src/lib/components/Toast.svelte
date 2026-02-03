<script lang="ts">
	import { TOAST_DURATION } from '$lib/constants';

	interface Props {
		show?: boolean;
		message?: string;
		type?: 'success' | 'error' | 'info' | 'warning';
		duration?: number;
	}

	let { show = $bindable(false), message = 'Added to Library', type = 'success', duration = TOAST_DURATION }: Props = $props();

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

	const icons: Record<string, string> = {
		success: 'M5 13l4 4L19 7',
		error: 'M6 18L18 6M6 6l12 12',
		info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
		warning: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z'
	};
</script>

{#if show}
	<div class="toast toast-end toast-bottom">
		<div class="alert {alertClasses[type]}">
			<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d={icons[type]} />
			</svg>
			<span>{message}</span>
		</div>
	</div>
{/if}

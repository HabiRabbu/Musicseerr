<script lang="ts">
	import { Music, Play } from 'lucide-svelte';
	import { getQueueCachedData } from '$lib/utils/discoverQueueCache';

	let { onLaunch }: { onLaunch: () => void } = $props();

	let hasCachedQueue = $state(false);

	$effect(() => {
		const cached = getQueueCachedData();
		hasCachedQueue = (cached?.data?.items?.length ?? 0) > 0;
	});
</script>

<div class="discover-queue-card">
	<div class="discover-queue-content">
		<div class="discover-queue-icon">
			<Music class="h-10 w-10" strokeWidth={1.5} />
		</div>
		<div class="discover-queue-text">
			<h3 class="text-xl font-bold text-base-content">Discover Queue</h3>
			<p class="text-sm text-base-content/60">Find new music tailored to your taste</p>
		</div>
		<button class="btn btn-primary btn-lg" onclick={onLaunch}>
			<Play class="h-5 w-5" strokeWidth={2} />
			{hasCachedQueue ? 'Resume Discover Queue' : 'Launch Discover Queue'}
		</button>
	</div>
</div>

<style>
	.discover-queue-card {
		width: 100%;
		border-radius: 1rem;
		padding: 3rem 2rem;
		background: linear-gradient(
			135deg,
			rgba(56, 189, 248, 0.12) 0%,
			rgba(99, 102, 241, 0.1) 50%,
			rgba(168, 85, 247, 0.08) 100%
		);
		border: 1px solid rgba(56, 189, 248, 0.2);
		box-shadow:
			0 0 30px rgba(56, 189, 248, 0.06),
			inset 0 1px 0 rgba(255, 255, 255, 0.05);
		position: relative;
		overflow: hidden;
	}

	.discover-queue-card::before {
		content: '';
		position: absolute;
		top: -50%;
		left: -50%;
		width: 200%;
		height: 200%;
		background:
			radial-gradient(circle at 30% 40%, rgba(56, 189, 248, 0.08) 0%, transparent 50%),
			radial-gradient(circle at 70% 60%, rgba(168, 85, 247, 0.06) 0%, transparent 50%);
		pointer-events: none;
	}

	.discover-queue-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.25rem;
		text-align: center;
		position: relative;
		z-index: 1;
	}

	.discover-queue-icon {
		color: var(--color-primary);
		opacity: 0.7;
	}

	.discover-queue-text {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
</style>

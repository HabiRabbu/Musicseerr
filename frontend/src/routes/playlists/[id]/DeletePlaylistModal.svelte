<script lang="ts">
	interface Props {
		playlistName: string;
		deleting: boolean;
		onconfirm: () => void;
	}

	let { playlistName, deleting, onconfirm }: Props = $props();

	let dialogEl = $state<HTMLDialogElement | null>(null);

	export function showModal() {
		dialogEl?.showModal();
	}
</script>

<dialog bind:this={dialogEl} class="modal">
	<div class="modal-box">
		<h3 class="text-lg font-bold">Delete "{playlistName}"?</h3>
		<p class="py-4 text-base-content/70">
			This will permanently remove the playlist and all its tracks. This action cannot be undone.
		</p>
		<div class="modal-action">
			<form method="dialog">
				<button class="btn btn-ghost">Cancel</button>
			</form>
			<button class="btn btn-error" onclick={onconfirm} disabled={deleting}>
				{#if deleting}
					<span class="loading loading-spinner loading-xs"></span>
				{/if}
				Delete
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button>close</button>
	</form>
</dialog>

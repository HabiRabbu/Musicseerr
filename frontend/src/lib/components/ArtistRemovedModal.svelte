<script lang="ts">
	interface Props {
		artistName: string;
		onclose: () => void;
	}

	let { artistName, onclose }: Props = $props();

	let dialogEl: HTMLDialogElement | undefined = $state();

	$effect(() => {
		if (dialogEl && artistName) {
			dialogEl.showModal();
		}
	});

	function handleClose() {
		dialogEl?.close();
		onclose();
	}
</script>

<dialog bind:this={dialogEl} class="modal" onclose={handleClose}>
	<div class="modal-box max-w-md">
		<h3 class="text-lg font-bold">Artist Removed</h3>
		<p class="py-4 text-base-content/70">
			<span class="font-semibold text-base-content">{artistName}</span> was also removed from your library
			as they had no remaining albums.
		</p>
		<div class="modal-action">
			<button class="btn btn-primary" onclick={handleClose}>OK</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button>close</button>
	</form>
</dialog>

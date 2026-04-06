<script lang="ts">
	import { getAlbumRemovePreview, removeAlbum } from '$lib/utils/albumRemove';

	interface Props {
		albumTitle: string;
		artistName: string;
		musicbrainzId: string;
		ondeleted: (result: { artist_removed: boolean; artist_name?: string | null }) => void;
		onclose: () => void;
	}

	let { albumTitle, artistName, musicbrainzId, ondeleted, onclose }: Props = $props();

	let dialogEl: HTMLDialogElement | undefined = $state();
	let deleteFiles = $state(false);
	let removing = $state(false);
	let loadingPreview = $state(false);
	let willRemoveArtist = $state(false);
	let previewArtistName = $state<string | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		if (dialogEl && musicbrainzId) {
			dialogEl.showModal();
			loadRemovalPreview();
		}
	});

	async function loadRemovalPreview() {
		loadingPreview = true;
		const preview = await getAlbumRemovePreview(musicbrainzId);
		if (preview.success) {
			willRemoveArtist = preview.artist_will_be_removed;
			previewArtistName = preview.artist_name ?? artistName;
		}
		loadingPreview = false;
	}

	function handleClose() {
		dialogEl?.close();
		onclose();
	}

	async function handleRemove() {
		removing = true;
		error = null;

		const result = await removeAlbum(musicbrainzId, deleteFiles);

		if (result.success) {
			dialogEl?.close();
			ondeleted({
				artist_removed: result.artist_removed,
				artist_name: result.artist_name
			});
		} else {
			error = result.error || "Couldn't remove this album";
		}

		removing = false;
	}
</script>

<dialog bind:this={dialogEl} class="modal" onclose={handleClose}>
	<div class="modal-box max-w-md">
		<h3 class="text-lg font-bold">Remove Album</h3>
		<p class="py-4 text-base-content/70">
			Remove <span class="font-semibold text-base-content">{albumTitle}</span> by
			<span class="font-semibold text-base-content">{artistName}</span> from your library?
		</p>

		{#if loadingPreview}
			<div class="alert alert-info mt-3 text-sm">
				<span>Checking artist impact...</span>
			</div>
		{:else if willRemoveArtist}
			<div class="alert alert-warning mt-3 text-sm">
				<span>
					This will also remove <span class="font-semibold">{previewArtistName || artistName}</span> from
					your library.
				</span>
			</div>
		{/if}

		<label class="label cursor-pointer justify-start gap-3">
			<input
				type="checkbox"
				class="checkbox checkbox-error checkbox-sm"
				bind:checked={deleteFiles}
			/>
			<span class="label-text">Also delete local files</span>
		</label>

		{#if error}
			<div class="alert alert-error mt-3 text-sm">
				<span>{error}</span>
			</div>
		{/if}

		<div class="modal-action">
			<button class="btn btn-ghost" onclick={handleClose} disabled={removing}> Cancel </button>
			<button class="btn btn-error" onclick={handleRemove} disabled={removing}>
				{#if removing}
					<span class="loading loading-spinner loading-sm"></span>
					Removing...
				{:else}
					Remove
				{/if}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button>close</button>
	</form>
</dialog>

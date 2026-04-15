<script lang="ts">
	import {
		getUpdateCheckQuery,
		getVersionQuery,
		getReleaseHistoryQuery
	} from '$lib/queries/VersionQuery.svelte';
	import UpdateBanner from '$lib/components/UpdateBanner.svelte';
	import WhatsNewModal from '$lib/components/WhatsNewModal.svelte';

	let { updateAvailable = $bindable(false) }: { updateAvailable: boolean } = $props();

	const updateCheckQuery = getUpdateCheckQuery();
	const versionQuery = getVersionQuery();
	const releaseHistoryQuery = getReleaseHistoryQuery();

	const currentVersion = $derived(versionQuery.data?.version ?? null);
	const buildDate = $derived(versionQuery.data?.build_date ?? null);
	const isDev = $derived(currentVersion === 'dev' || currentVersion === 'hosting-local');
	const currentRelease = $derived(
		releaseHistoryQuery.data?.find((r) => r.tag_name === currentVersion) ??
			(isDev ? releaseHistoryQuery.data?.[0] : null) ??
			null
	);

	$effect(() => {
		updateAvailable = updateCheckQuery.data?.update_available ?? false;
	});
</script>

<UpdateBanner
	updateAvailable={updateCheckQuery.data?.update_available ?? false}
	latestVersion={updateCheckQuery.data?.latest_version ?? null}
/>
<WhatsNewModal
	{currentVersion}
	{buildDate}
	releaseTag={currentRelease?.tag_name ?? null}
	releaseBody={currentRelease?.body ?? null}
	releaseName={currentRelease?.name ?? null}
/>

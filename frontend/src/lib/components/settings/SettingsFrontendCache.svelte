<script lang="ts">
	import type { AdvancedSettingsForm } from './advanced-settings-types';
	import SettingsNumberField from './SettingsNumberField.svelte';

	let { data = $bindable() }: { data: AdvancedSettingsForm } = $props();
</script>

<div class="alert alert-info alert-soft mb-4">
	<span class="text-sm"
		>Choose how long pages stay fresh in your browser. Lower values update sooner. Higher values
		feel faster when you come back.</span
	>
</div>
<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 pt-2">
	<SettingsNumberField
		label="Home Page"
		description="Default: 5 minutes"
		bind:value={data.frontend_ttl_home}
		min={1}
		max={60}
		unit="min"
	/>
	<SettingsNumberField
		label="Discover Page"
		description="Default: 30 minutes"
		bind:value={data.frontend_ttl_discover}
		min={1}
		max={1440}
		unit="min"
	/>
	<SettingsNumberField
		label="Library"
		description="Default: 5 minutes"
		bind:value={data.frontend_ttl_library}
		min={1}
		max={60}
		unit="min"
	/>
	<SettingsNumberField
		label="Recently Added"
		description="Default: 5 minutes"
		bind:value={data.frontend_ttl_recently_added}
		min={1}
		max={60}
		unit="min"
	/>
	<SettingsNumberField
		label="Discover Queue"
		description="Default: 24 hours"
		bind:value={data.frontend_ttl_discover_queue}
		min={60}
		max={10080}
		unit="min"
	/>
	<SettingsNumberField
		label="Search & Discovery"
		description="Default: 5 minutes"
		bind:value={data.frontend_ttl_search}
		min={1}
		max={60}
		unit="min"
	/>
	<SettingsNumberField
		label="Local Files Sidebar"
		description="Default: 2 minutes"
		bind:value={data.frontend_ttl_local_files_sidebar}
		min={1}
		max={60}
		unit="min"
	/>
	<SettingsNumberField
		label="Jellyfin Sidebar"
		description="Default: 2 minutes"
		bind:value={data.frontend_ttl_jellyfin_sidebar}
		min={1}
		max={60}
		unit="min"
	/>
	<SettingsNumberField
		label="Playlist Sources"
		description="Default: 15 minutes"
		bind:value={data.frontend_ttl_playlist_sources}
		min={1}
		max={60}
		unit="min"
	/>
</div>

<script lang="ts">
	import BaseImage from './BaseImage.svelte';

	interface Props {
		mbid: string;
		alt?: string;
		size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'hero' | 'full';
		lazy?: boolean;
		showPlaceholder?: boolean;
		className?: string;
		rounded?: 'none' | 'sm' | 'md' | 'lg' | 'xl' | 'full';
		remoteUrl?: string | null;
	}

	let {
		mbid,
		alt = 'Artist',
		size = 'md',
		lazy = true,
		showPlaceholder = true,
		className = '',
		rounded = 'full',
		remoteUrl = null
	}: Props = $props();
</script>

<BaseImage
	{mbid}
	{alt}
	{size}
	{lazy}
	{showPlaceholder}
	{className}
	{rounded}
	{remoteUrl}
	imageType="artist"
/>

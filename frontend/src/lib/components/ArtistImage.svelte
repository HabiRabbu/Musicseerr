<script lang="ts">
	import BaseImage from './BaseImage.svelte';

	export let mbid: string;
	export let alt: string = 'Artist';
	export let size: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'hero' | 'full' = 'md';
	export let lazy: boolean = true;
	export let showPlaceholder: boolean = true;
	export let className: string = '';
	export let rounded: 'none' | 'sm' | 'md' | 'lg' | 'xl' | 'full' = 'full';
</script>

<BaseImage
	{mbid}
	{alt}
	{size}
	{lazy}
	{showPlaceholder}
	{className}
	{rounded}
	imageType="artist"
/>

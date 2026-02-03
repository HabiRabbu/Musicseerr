<script lang="ts">
	import BaseImage from './BaseImage.svelte';

	export let mbid: string;
	export let alt: string = 'Album';
	export let size: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'hero' | 'full' = 'md';
	export let lazy: boolean = true;
	export let showPlaceholder: boolean = true;
	export let className: string = '';
	export let rounded: 'none' | 'sm' | 'md' | 'lg' | 'xl' | 'full' = 'lg';
	export let customUrl: string | null = null;
</script>

<BaseImage
	{mbid}
	{alt}
	{size}
	{lazy}
	{showPlaceholder}
	{className}
	{rounded}
	{customUrl}
	imageType="album"
/>

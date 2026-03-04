<script lang="ts" module>
	let activeMenu: HTMLDetailsElement | null = null;

	export function closeAllMenus() {
		if (activeMenu) {
			activeMenu.open = false;
			activeMenu = null;
		}
	}
</script>

<script lang="ts">
	import { EllipsisVertical } from 'lucide-svelte';
	import type { Component, SvelteComponent } from 'svelte';

	export interface MenuItem {
		label: string;
		icon: Component<any> | (new (...args: any[]) => SvelteComponent<any>);
		onclick: () => void;
		disabled?: boolean;
		className?: string;
	}

	interface Props {
		items: MenuItem[];
		position?: 'start' | 'end';
		size?: 'xs' | 'sm';
	}

	let { items, position = 'end', size = 'sm' }: Props = $props();
	let detailsEl = $state<HTMLDetailsElement | null>(null);
	let isOpen = $state(false);

	function handleItemClick(item: MenuItem) {
		if (item.disabled) return;
		if (detailsEl) detailsEl.open = false;
		item.onclick();
	}

	function handleClickOutside(e: MouseEvent) {
		if (detailsEl?.open && !detailsEl.contains(e.target as Node)) {
			detailsEl.open = false;
		}
	}

	function handleToggle() {
		const nowOpen = detailsEl?.open ?? false;
		if (nowOpen) {
			if (activeMenu && activeMenu !== detailsEl) {
				activeMenu.open = false;
			}
			activeMenu = detailsEl;
		} else if (activeMenu === detailsEl) {
			activeMenu = null;
		}
		isOpen = nowOpen;
	}

	$effect(() => {
		if (isOpen) {
			document.addEventListener('click', handleClickOutside);
			return () => document.removeEventListener('click', handleClickOutside);
		}
	});
</script>

<details
	bind:this={detailsEl}
	class="dropdown {position === 'start' ? 'dropdown-start' : 'dropdown-end'}"
	ontoggle={handleToggle}
>
	<summary
		class="btn btn-ghost btn-circle {size === 'xs' ? 'btn-xs' : 'btn-sm'}"
		aria-haspopup="menu"
		aria-label="More actions"
		onclick={(e: MouseEvent) => e.stopPropagation()}
	>
		<EllipsisVertical class={size === 'xs' ? 'h-3.5 w-3.5' : 'h-4 w-4'} />
	</summary>
	<ul
		class="dropdown-content menu bg-base-200/95 backdrop-blur-md rounded-box shadow-lg z-50 w-52 p-2"
		role="menu"
	>
		{#each items as item}
			<li>
				<button
					role="menuitem"
					class="{item.disabled ? 'opacity-50 cursor-not-allowed' : ''} {item.className ?? ''}"
					disabled={item.disabled}
					aria-disabled={item.disabled ? 'true' : undefined}
					onclick={(e: MouseEvent) => {
						e.stopPropagation();
						handleItemClick(item);
					}}
				>
					<item.icon class="h-4 w-4" />
					{item.label}
				</button>
			</li>
		{/each}
	</ul>
</details>

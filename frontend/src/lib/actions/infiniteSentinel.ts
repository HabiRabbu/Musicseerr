type InfiniteSentinelOptions = {
	enabled: boolean;
	onIntersect: () => void;
	rootMargin?: string;
};

export function infiniteSentinel(node: HTMLElement, options: InfiniteSentinelOptions) {
	let observer: IntersectionObserver | null = null;

	function disconnect() {
		observer?.disconnect();
		observer = null;
	}

	function setup(nextOptions: InfiniteSentinelOptions) {
		disconnect();
		if (!nextOptions.enabled) return;

		observer = new IntersectionObserver(
			(entries) => {
				if (entries.some((entry) => entry.isIntersecting)) {
					nextOptions.onIntersect();
				}
			},
			{ rootMargin: nextOptions.rootMargin ?? '400px 0px' }
		);

		observer.observe(node);
	}

	setup(options);

	return {
		update(nextOptions: InfiniteSentinelOptions) {
			setup(nextOptions);
		},
		destroy() {
			disconnect();
		}
	};
}

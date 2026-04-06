import { browser } from '$app/environment';

let sharedObserver: IntersectionObserver | null = null;
let observerRefCount = 0;
const pendingImages: Set<HTMLImageElement> = new Set();

export function cancelPendingImages() {
	pendingImages.forEach((img) => {
		if (sharedObserver) {
			sharedObserver.unobserve(img);
		}
		img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
	});
	pendingImages.clear();
}

function getSharedObserver(): IntersectionObserver | null {
	if (!browser) return null;

	if (!sharedObserver) {
		sharedObserver = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) {
						const img = entry.target as HTMLImageElement;
						const src = img.dataset.src;
						if (src && img.src !== src) {
							img.src = src;
							sharedObserver?.unobserve(img);
						}
					}
				});
			},
			{
				rootMargin: '200px',
				threshold: 0.01
			}
		);
	}

	observerRefCount++;
	return sharedObserver;
}

function releaseSharedObserver() {
	observerRefCount--;
	if (observerRefCount <= 0 && sharedObserver) {
		sharedObserver.disconnect();
		sharedObserver = null;
		observerRefCount = 0;
	}
}

export function lazyImage(img: HTMLImageElement) {
	const observer = getSharedObserver();

	pendingImages.add(img);

	if (observer) {
		observer.observe(img);
	} else {
		const src = img.dataset.src;
		if (src) {
			img.src = src;
			pendingImages.delete(img);
		}
	}

	const handleLoad = () => pendingImages.delete(img);
	const handleError = () => pendingImages.delete(img);
	img.addEventListener('load', handleLoad);
	img.addEventListener('error', handleError);

	return {
		update() {
			if (observer) {
				observer.unobserve(img);
				pendingImages.add(img);
				observer.observe(img);
			}
		},
		destroy() {
			img.removeEventListener('load', handleLoad);
			img.removeEventListener('error', handleError);
			pendingImages.delete(img);
			if (observer) {
				observer.unobserve(img);
			}
			releaseSharedObserver();
		}
	};
}

export function resetLazyImage(img: HTMLImageElement, newSrc: string) {
	img.classList.add('opacity-0');
	img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
	img.dataset.src = newSrc;

	if (sharedObserver) {
		sharedObserver.unobserve(img);
		pendingImages.add(img);
		sharedObserver.observe(img);
	}
}

import { serviceStatusStore } from '$lib/stores/serviceStatus';

let controller = new AbortController();

export function getNavigationSignal(): AbortSignal {
	return controller.signal;
}

export function abortAllPageRequests(): void {
	controller.abort();
	controller = new AbortController();
}

export async function pageFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
	if (typeof window === 'undefined') {
		throw new Error('Can never happen, we are running in SPA mode');
	}
	const navSignal = getNavigationSignal();
	const existingSignal = init?.signal;
	const signal = existingSignal ? AbortSignal.any([navSignal, existingSignal]) : navSignal;
	const response = await fetch(input, { ...init, signal });

	const degradedHeader = response.headers.get('X-Degraded-Services');
	if (degradedHeader) {
		serviceStatusStore.recordFromHeader(degradedHeader);
	}

	return response;
}

export { isAbortError } from '$lib/utils/errorHandling';

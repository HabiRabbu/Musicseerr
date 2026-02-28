import type {
	ActiveRequestsResponse,
	RequestCountChangedDetail,
	RequestHistoryResponse
} from '$lib/types';

export type { ActiveRequestsResponse, RequestCountChangedDetail, RequestHistoryResponse } from '$lib/types';

export function notifyRequestCountChanged(count?: number): void {
	if (typeof window === 'undefined') return;

	if (typeof count === 'number') {
		window.dispatchEvent(
			new CustomEvent<RequestCountChangedDetail>('request-count-changed', {
				detail: { count }
			})
		);
		return;
	}

	window.dispatchEvent(new CustomEvent('request-count-changed'));
}

export async function fetchActiveRequests(signal?: AbortSignal): Promise<ActiveRequestsResponse> {
	const res = await fetch('/api/requests/active', { signal });
	if (!res.ok) throw new Error('Failed to fetch active requests');
	return res.json();
}

export async function fetchRequestHistory(
	page: number = 1,
	pageSize: number = 20,
	status?: string,
	signal?: AbortSignal
): Promise<RequestHistoryResponse> {
	const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
	if (status) params.set('status', status);
	const res = await fetch(`/api/requests/history?${params}`, { signal });
	if (!res.ok) throw new Error('Failed to fetch request history');
	return res.json();
}

export async function cancelRequest(
	musicbrainzId: string
): Promise<{ success: boolean; message: string }> {
	const res = await fetch(`/api/requests/active/${musicbrainzId}`, {
		method: 'DELETE'
	});
	if (!res.ok) throw new Error('Failed to cancel request');
	const data = await res.json();
	notifyRequestCountChanged();
	return data;
}

export async function retryRequest(
	musicbrainzId: string
): Promise<{ success: boolean; message: string }> {
	const res = await fetch(`/api/requests/retry/${musicbrainzId}`, {
		method: 'POST'
	});
	if (!res.ok) throw new Error('Failed to retry request');
	const data = await res.json();
	notifyRequestCountChanged();
	return data;
}

export async function clearHistoryItem(
	musicbrainzId: string
): Promise<{ success: boolean }> {
	const res = await fetch(`/api/requests/history/${musicbrainzId}`, {
		method: 'DELETE'
	});
	if (!res.ok) throw new Error('Failed to clear history item');
	return res.json();
}

export async function fetchActiveRequestCount(): Promise<number> {
	const res = await fetch('/api/requests/active/count');
	if (!res.ok) throw new Error('Failed to fetch active request count');
	const data = await res.json();
	return data.count ?? 0;
}

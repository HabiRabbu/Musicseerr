export type Abortable = {
	readonly signal: AbortSignal;
	abort: () => void;
	reset: () => AbortSignal;
	isAborted: () => boolean;
};

export function createAbortable(): Abortable {
	let controller = new AbortController();

	return {
		get signal() {
			return controller.signal;
		},
		abort() {
			controller.abort();
		},
		reset() {
			controller.abort();
			controller = new AbortController();
			return controller.signal;
		},
		isAborted() {
			return controller.signal.aborted;
		}
	};
}

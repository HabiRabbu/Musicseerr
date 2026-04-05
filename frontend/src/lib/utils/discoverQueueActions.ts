export interface QueueCloseState {
	queueLength: number;
	isLastItem: boolean;
}

/**
 * Determines whether to save or remove the queue from localStorage on close/navigate.
 * Returns 'save' if the queue has items and we're not at the last item,
 * otherwise returns 'remove'.
 */
export function resolveQueueCloseAction(state: QueueCloseState): 'save' | 'remove' {
	if (state.queueLength > 0 && !state.isLastItem) {
		return 'save';
	}
	return 'remove';
}

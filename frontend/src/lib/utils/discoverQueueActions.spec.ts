import { describe, it, expect } from 'vitest';
import { resolveQueueCloseAction } from './discoverQueueActions';

describe('resolveQueueCloseAction', () => {
	it('returns save when queue has items and not at last item', () => {
		expect.assertions(1);
		expect(resolveQueueCloseAction({ queueLength: 5, isLastItem: false })).toBe('save');
	});

	it('returns remove when queue is empty', () => {
		expect.assertions(1);
		expect(resolveQueueCloseAction({ queueLength: 0, isLastItem: false })).toBe('remove');
	});

	it('returns remove when at last item', () => {
		expect.assertions(1);
		expect(resolveQueueCloseAction({ queueLength: 5, isLastItem: true })).toBe('remove');
	});

	it('returns remove when queue is empty and at last item', () => {
		expect.assertions(1);
		expect(resolveQueueCloseAction({ queueLength: 0, isLastItem: true })).toBe('remove');
	});

	it('returns save when queue has 1 item and not at last item', () => {
		expect.assertions(1);
		expect(resolveQueueCloseAction({ queueLength: 1, isLastItem: false })).toBe('save');
	});

	it('returns remove when queue has 1 item and at last item', () => {
		expect.assertions(1);
		expect(resolveQueueCloseAction({ queueLength: 1, isLastItem: true })).toBe('remove');
	});
});

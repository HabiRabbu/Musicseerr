import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { playbackToast } from './playbackToast.svelte';

describe('playbackToast', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		playbackToast.dismiss();
	});

	afterEach(() => {
		playbackToast.dismiss();
		vi.useRealTimers();
	});

	it('starts hidden', () => {
		expect(playbackToast.visible).toBe(false);
		expect(playbackToast.message).toBe('');
	});

	it('shows a toast with message and type', () => {
		playbackToast.show('Track skipped', 'warning');

		expect(playbackToast.visible).toBe(true);
		expect(playbackToast.message).toBe('Track skipped');
		expect(playbackToast.type).toBe('warning');
	});

	it('auto-dismisses after 3 seconds', async () => {
		playbackToast.show('Error occurred', 'error');
		expect(playbackToast.visible).toBe(true);

		await vi.advanceTimersByTimeAsync(3000);

		expect(playbackToast.visible).toBe(false);
	});

	it('resets timer when showing a new toast before dismiss', async () => {
		playbackToast.show('First message', 'info');
		await vi.advanceTimersByTimeAsync(2000);

		playbackToast.show('Second message', 'warning');
		expect(playbackToast.message).toBe('Second message');

		await vi.advanceTimersByTimeAsync(2000);
		expect(playbackToast.visible).toBe(true);

		await vi.advanceTimersByTimeAsync(1000);
		expect(playbackToast.visible).toBe(false);
	});

	it('can be manually dismissed', () => {
		playbackToast.show('Some message', 'info');
		expect(playbackToast.visible).toBe(true);

		playbackToast.dismiss();
		expect(playbackToast.visible).toBe(false);
	});

	it('defaults type to info when not specified', () => {
		playbackToast.show('Info toast');
		expect(playbackToast.type).toBe('info');
	});
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const { mockApiGet, mockApiPut, mockApiPost, mockSetStatus } = vi.hoisted(() => ({
	mockApiGet: vi.fn(),
	mockApiPut: vi.fn(),
	mockApiPost: vi.fn(),
	mockSetStatus: vi.fn()
}));

vi.mock('$lib/api/client', () => {
	class ApiError extends Error {
		status: number;
		code: string;
		details: unknown;
		constructor(status: number, code: string, message: string, details?: unknown) {
			super(message);
			this.name = 'ApiError';
			this.status = status;
			this.code = code;
			this.details = details;
		}
	}
	return {
		api: {
			global: { get: mockApiGet, put: mockApiPut, post: mockApiPost },
			get: mockApiGet,
			put: mockApiPut,
			post: mockApiPost
		},
		ApiError
	};
});

vi.mock('$lib/utils/errorHandling', () => ({
	isAbortError: (e: unknown) =>
		e instanceof DOMException && (e as DOMException).name === 'AbortError'
}));

vi.mock('$lib/stores/integration', () => ({
	integrationStore: { setStatus: mockSetStatus }
}));

import { createSettingsForm } from './settingsForm.svelte';

interface TestSettings {
	url: string;
	enabled: boolean;
}

const defaultConfig = {
	loadEndpoint: '/api/v1/settings/test',
	saveEndpoint: '/api/v1/settings/test'
};

describe('createSettingsForm', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('initializes with loading=true and null data', () => {
		const form = createSettingsForm<TestSettings>(defaultConfig);
		expect(form.loading).toBe(true);
		expect(form.data).toBeNull();
		expect(form.message).toBe('');
		form.cleanup();
	});

	describe('load', () => {
		it('fetches data and sets state on success', async () => {
			const data = { url: 'http://test', enabled: true };
			mockApiGet.mockResolvedValueOnce(data);
			const form = createSettingsForm<TestSettings>(defaultConfig);
			await form.load();

			expect(mockApiGet).toHaveBeenCalledWith('/api/v1/settings/test');
			expect(form.data).toEqual(data);
			expect(form.loading).toBe(false);
			expect(form.message).toBe('');
			form.cleanup();
		});

		it('tracks wasAlreadyEnabled from enabledField', async () => {
			mockApiGet.mockResolvedValueOnce({ url: 'http://test', enabled: true });
			const form = createSettingsForm<TestSettings>({ ...defaultConfig, enabledField: 'enabled' });
			await form.load();

			expect(form.wasAlreadyEnabled).toBe(true);
			form.cleanup();
		});

		it('shows error message on failure', async () => {
			mockApiGet.mockRejectedValueOnce(new Error('Network error'));
			const form = createSettingsForm<TestSettings>(defaultConfig);
			await form.load();

			expect(form.loading).toBe(false);
			expect(form.message).toBe("Couldn't load your settings");
			expect(form.messageType).toBe('error');
			form.cleanup();
		});

		it('uses defaultValue on load failure', async () => {
			const defaultValue = { url: '', enabled: false };
			mockApiGet.mockRejectedValueOnce(new Error('fail'));
			const form = createSettingsForm<TestSettings>({
				...defaultConfig,
				defaultValue
			});
			await form.load();

			expect(form.data).toEqual(defaultValue);
			form.cleanup();
		});
	});

	describe('save', () => {
		it('PUTs data and returns true on success', async () => {
			const data = { url: 'http://test', enabled: true };
			mockApiGet.mockResolvedValueOnce(data);
			mockApiPut.mockResolvedValueOnce(data);

			const form = createSettingsForm<TestSettings>(defaultConfig);
			await form.load();
			const result = await form.save();

			expect(mockApiPut).toHaveBeenCalledWith('/api/v1/settings/test', data);
			expect(result).toBe(true);
			expect(form.message).toBe('Settings saved');
			expect(form.messageType).toBe('success');
			form.cleanup();
		});

		it('auto-clears success message after 5s', async () => {
			const data = { url: 'http://test', enabled: true };
			mockApiGet.mockResolvedValueOnce(data);
			mockApiPut.mockResolvedValueOnce(data);

			const form = createSettingsForm<TestSettings>(defaultConfig);
			await form.load();
			await form.save();

			expect(form.message).toBe('Settings saved');
			vi.advanceTimersByTime(5000);
			expect(form.message).toBe('');
			form.cleanup();
		});

		it('returns false on failure', async () => {
			mockApiGet.mockResolvedValueOnce({ url: '', enabled: false });
			mockApiPut.mockRejectedValueOnce(new Error('save failed'));

			const form = createSettingsForm<TestSettings>(defaultConfig);
			await form.load();
			const result = await form.save();

			expect(result).toBe(false);
			expect(form.message).toBe("Couldn't save your settings");
			expect(form.messageType).toBe('error');
			form.cleanup();
		});

		it('uses ApiError message on failure', async () => {
			const { ApiError } = await import('$lib/api/client');
			mockApiGet.mockResolvedValueOnce({ url: '', enabled: false });
			mockApiPut.mockRejectedValueOnce(new ApiError(400, 'VALIDATION', 'Invalid URL format'));

			const form = createSettingsForm<TestSettings>(defaultConfig);
			await form.load();
			const result = await form.save();

			expect(result).toBe(false);
			expect(form.message).toBe('Invalid URL format');
			form.cleanup();
		});

		it('refreshes integration status when configured', async () => {
			const data = { url: 'http://test', enabled: true };
			mockApiGet.mockResolvedValueOnce(data);
			mockApiPut.mockResolvedValueOnce(data);
			mockApiGet.mockResolvedValueOnce({ jellyfin: true });

			const form = createSettingsForm<TestSettings>({
				...defaultConfig,
				refreshIntegration: true
			});
			await form.load();
			await form.save();

			expect(mockSetStatus).toHaveBeenCalledWith({ jellyfin: true });
			form.cleanup();
		});

		it('calls afterSave callback on success', async () => {
			const afterSave = vi.fn();
			const data = { url: 'http://test', enabled: true };
			mockApiGet.mockResolvedValueOnce(data);
			mockApiPut.mockResolvedValueOnce(data);

			const form = createSettingsForm<TestSettings>({
				...defaultConfig,
				afterSave
			});
			await form.load();
			await form.save();

			expect(afterSave).toHaveBeenCalledWith(data);
			form.cleanup();
		});

		it('updates wasAlreadyEnabled after save', async () => {
			mockApiGet.mockResolvedValueOnce({ url: '', enabled: false });
			mockApiPut.mockResolvedValueOnce({ url: 'http://new', enabled: true });

			const form = createSettingsForm<TestSettings>({
				...defaultConfig,
				enabledField: 'enabled'
			});
			await form.load();
			expect(form.wasAlreadyEnabled).toBe(false);

			await form.save();
			expect(form.wasAlreadyEnabled).toBe(true);
			form.cleanup();
		});
	});

	describe('test', () => {
		it('POSTs data to test endpoint and sets testResult', async () => {
			const data = { url: 'http://test', enabled: true };
			const testData = { success: true, message: 'Connected' };
			mockApiGet.mockResolvedValueOnce(data);
			mockApiPost.mockResolvedValueOnce(testData);

			const form = createSettingsForm<TestSettings>({
				...defaultConfig,
				testEndpoint: '/api/v1/settings/test/verify'
			});
			await form.load();
			await form.test();

			expect(mockApiPost).toHaveBeenCalledWith('/api/v1/settings/test/verify', data);
			expect(form.testResult).toEqual(testData);
			expect(form.testing).toBe(false);
			form.cleanup();
		});

		it('calls afterTest callback', async () => {
			const afterTest = vi.fn();
			mockApiGet.mockResolvedValueOnce({ url: 'http://test', enabled: true });
			mockApiPost.mockResolvedValueOnce({ success: true });

			const form = createSettingsForm<TestSettings>({
				...defaultConfig,
				testEndpoint: '/api/v1/settings/test/verify',
				afterTest
			});
			await form.load();
			await form.test();

			expect(afterTest).toHaveBeenCalledWith({ success: true });
			form.cleanup();
		});

		it('sets failure testResult on error', async () => {
			mockApiGet.mockResolvedValueOnce({ url: 'http://test', enabled: true });
			mockApiPost.mockRejectedValueOnce(new Error('timeout'));

			const form = createSettingsForm<TestSettings>({
				...defaultConfig,
				testEndpoint: '/api/v1/settings/test/verify'
			});
			await form.load();
			await form.test();

			expect(form.testResult).toEqual({
				success: false,
				valid: false,
				message: "Couldn't test the connection"
			});
			form.cleanup();
		});

		it('does nothing without testEndpoint', async () => {
			mockApiGet.mockResolvedValueOnce({ url: 'http://test', enabled: true });
			const form = createSettingsForm<TestSettings>(defaultConfig);
			await form.load();
			await form.test();

			expect(mockApiPost).not.toHaveBeenCalled();
			form.cleanup();
		});
	});

	describe('cleanup', () => {
		it('clears pending auto-clear timer', async () => {
			const data = { url: 'http://test', enabled: true };
			mockApiGet.mockResolvedValueOnce(data);
			mockApiPut.mockResolvedValueOnce(data);

			const form = createSettingsForm<TestSettings>(defaultConfig);
			await form.load();
			await form.save();
			expect(form.message).toBe('Settings saved');

			form.cleanup();
			vi.advanceTimersByTime(5000);
			expect(form.message).toBe('Settings saved');
		});
	});
});

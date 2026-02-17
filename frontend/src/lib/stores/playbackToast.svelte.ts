const TOAST_AUTO_DISMISS_MS = 3000;

type ToastType = 'error' | 'warning' | 'info';

function createPlaybackToastStore() {
	let visible = $state(false);
	let message = $state('');
	let type = $state<ToastType>('info');
	let dismissTimer: ReturnType<typeof setTimeout> | null = null;

	function clearTimer(): void {
		if (dismissTimer) {
			clearTimeout(dismissTimer);
			dismissTimer = null;
		}
	}

	return {
		get visible() {
			return visible;
		},
		get message() {
			return message;
		},
		get type() {
			return type;
		},

		show(msg: string, toastType: ToastType = 'info'): void {
			clearTimer();
			message = msg;
			type = toastType;
			visible = true;
			dismissTimer = setTimeout(() => {
				visible = false;
				dismissTimer = null;
			}, TOAST_AUTO_DISMISS_MS);
		},

		dismiss(): void {
			clearTimer();
			visible = false;
		}
	};
}

export const playbackToast = createPlaybackToastStore();

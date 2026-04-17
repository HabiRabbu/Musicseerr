/**
 * Trigger a browser-native file download via an invisible anchor element.
 * The server's Content-Disposition header determines the saved filename.
 */
export function downloadFile(url: string): void {
	const a = document.createElement('a');
	a.href = url;
	a.download = '';
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
}

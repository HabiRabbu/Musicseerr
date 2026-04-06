export const DEFAULT_GRADIENT = 'from-base-300 via-base-200 to-base-100';

export async function extractDominantColor(imgUrl: string): Promise<string> {
	return new Promise((resolve) => {
		const img = new Image();
		img.crossOrigin = 'anonymous';
		img.onload = () => {
			try {
				const canvas = document.createElement('canvas');
				const ctx = canvas.getContext('2d');
				if (!ctx) {
					resolve(DEFAULT_GRADIENT);
					return;
				}

				canvas.width = 50;
				canvas.height = 50;
				ctx.drawImage(img, 0, 0, 50, 50);

				const imageData = ctx.getImageData(0, 0, 50, 50).data;
				let r = 0,
					g = 0,
					b = 0,
					count = 0;

				for (let i = 0; i < imageData.length; i += 16) {
					const pr = imageData[i];
					const pg = imageData[i + 1];
					const pb = imageData[i + 2];
					const pa = imageData[i + 3];

					if (pa > 128) {
						r += pr;
						g += pg;
						b += pb;
						count++;
					}
				}

				if (count > 0) {
					r = Math.round(r / count);
					g = Math.round(g / count);
					b = Math.round(b / count);

					const darkerR = Math.round(r * 0.3);
					const darkerG = Math.round(g * 0.3);
					const darkerB = Math.round(b * 0.3);

					resolve(
						`from-[rgb(${darkerR},${darkerG},${darkerB})] via-[rgb(${Math.round(r * 0.15)},${Math.round(g * 0.15)},${Math.round(b * 0.15)})] to-base-100`
					);
				} else {
					resolve(DEFAULT_GRADIENT);
				}
			} catch (_e) {
				resolve(DEFAULT_GRADIENT);
			}
		};
		img.onerror = () => resolve(DEFAULT_GRADIENT);
		img.src = imgUrl;
	});
}

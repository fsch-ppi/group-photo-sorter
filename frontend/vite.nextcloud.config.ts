import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import path from 'path';

export default defineConfig({
	plugins: [svelte()],
	build: {
		outDir: path.resolve(__dirname, '../'), // Output directly to the Nextcloud app root
		emptyOutDir: false, // Crucial: do not clear the Nextcloud app structure!
		lib: {
			entry: path.resolve(__dirname, 'src/main.ts'),
			name: 'GroupPhotoSorter',
			formats: ['iife'],
			fileName: () => 'js/group_photo_sorter.js'
		},
		rollupOptions: {
			output: {
				// Forces Vite to compile CSS file to css/group_photo_sorter.css
				assetFileNames: (assetInfo) => {
					if (assetInfo.name && assetInfo.name.endsWith('.css')) {
						return 'css/group_photo_sorter.[ext]';
					}
					return 'assets/[name].[ext]';
				}
			}
		}
	}
});

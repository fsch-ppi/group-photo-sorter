import AdminApp from './AdminApp.svelte';
import UploadApp from './UploadApp.svelte';
import './app.css';

// Mount Admin App
const adminEl = document.getElementById('group-photo-sorter-admin');
if (adminEl) {
	const apiBase = adminEl.getAttribute('data-api-base') || '';
	(window as any).groupPhotoSorter = {
		apiBase: apiBase
	};
	adminEl.innerHTML = '';
	new AdminApp({
		target: adminEl
	});
}

// Mount Guest Upload App
const uploadEl = document.getElementById('group-photo-sorter-upload');
if (uploadEl) {
	const apiBase = uploadEl.getAttribute('data-api-base') || '';
	const token = uploadEl.getAttribute('data-token') || '';
	(window as any).groupPhotoSorter = {
		apiBase: apiBase,
		token: token
	};
	uploadEl.innerHTML = '';
	new UploadApp({
		target: uploadEl,
		props: {
			token: token
		}
	});
}


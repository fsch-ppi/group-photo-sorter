<script lang="ts">
	import { base } from '$app/paths';
	import { folders, type PhotoFolder, type NamingFormat } from '$lib/api';
	import { onMount } from 'svelte';
	import { fly } from 'svelte/transition';

	let folderList: PhotoFolder[] = [];
	let namingFormats: NamingFormat[] = [];
	let loading = true;
	let error = '';

	// Toast notification state
	let toast = { show: false, message: '', type: 'success' as 'success' | 'error' };
	let toastTimeout: ReturnType<typeof setTimeout> | null = null;

	function showToast(message: string, type: 'success' | 'error' = 'success') {
		if (toastTimeout) clearTimeout(toastTimeout);
		toast = { show: true, message, type };
		toastTimeout = setTimeout(() => {
			toast = { ...toast, show: false };
		}, 3000);
	}

	// Modal state
	let showCreateModal = false;
	let showDetailModal = false;
	let selectedFolder: PhotoFolder | null = null;

	// Create form
	let createForm = {
		name: '',
		event_name: '',
		nextcloud_folder_path: '',
		naming_format: 'date_event',
		jpeg_quality: 90,
		readme_message: '',
		storage_limit_gb: null as number | null,
		show_download_link: true
	};
	let creating = false;
	let createError = '';

	onMount(async () => {
		await loadFolders();
		await loadNamingFormats();
	});

	async function loadFolders() {
		loading = true;
		error = '';
		try {
			folderList = await folders.list();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load folders';
		} finally {
			loading = false;
		}
	}

	async function loadNamingFormats() {
		try {
			namingFormats = await folders.namingFormats();
		} catch (e) {
			console.error('Failed to load naming formats:', e);
		}
	}

	async function createFolder() {
		creating = true;
		createError = '';
		try {
			const newFolder = await folders.create(createForm);
			folderList = [newFolder, ...folderList];
			showCreateModal = false;
			resetCreateForm();
		} catch (e) {
			createError = e instanceof Error ? e.message : 'Failed to create folder';
		} finally {
			creating = false;
		}
	}

	function resetCreateForm() {
		createForm = {
			name: '',
			event_name: '',
			nextcloud_folder_path: '',
			naming_format: 'date_event',
			jpeg_quality: 90,
			readme_message: '',
			storage_limit_gb: null,
			show_download_link: true
		};
	}

	async function openDetail(folder: PhotoFolder) {
		try {
			selectedFolder = await folders.get(folder.id);
			showDetailModal = true;
		} catch (e) {
			console.error('Failed to load folder details:', e);
		}
	}

	async function regenerateUploadToken() {
		if (!selectedFolder) return;
		try {
			const result = await folders.regenerateToken(selectedFolder.id);
			selectedFolder = { ...selectedFolder, share_token: result.share_token, upload_url: result.upload_url };
			folderList = folderList.map((f) => (f.id === selectedFolder?.id ? selectedFolder : f));
			showToast('Upload link regenerated');
		} catch (e) {
			console.error('Failed to regenerate token:', e);
			showToast('Failed to regenerate link', 'error');
		}
	}

	async function regenerateNextcloudShare() {
		if (!selectedFolder) return;
		try {
			const result = await folders.regenerateNextcloudShare(selectedFolder.id);
			selectedFolder = {
				...selectedFolder,
				nextcloud_share_token: result.nextcloud_share_token,
				nextcloud_share_url: result.nextcloud_share_url
			};
			folderList = folderList.map((f) => (f.id === selectedFolder?.id ? selectedFolder : f));
			showToast('Nextcloud share link regenerated');
		} catch (e) {
			console.error('Failed to regenerate Nextcloud share:', e);
			showToast('Failed to regenerate share link', 'error');
		}
	}

	async function toggleActive() {
		if (!selectedFolder) return;
		try {
			const updated = await folders.update(selectedFolder.id, { is_active: !selectedFolder.is_active });
			selectedFolder = updated;
			folderList = folderList.map((f) => (f.id === updated.id ? updated : f));
			showToast(updated.is_active ? 'Uploads enabled' : 'Uploads paused');
		} catch (e) {
			console.error('Failed to toggle active:', e);
			showToast('Failed to update status', 'error');
		}
	}

	async function toggleShowDownloadLink() {
		if (!selectedFolder) return;
		try {
			const updated = await folders.update(selectedFolder.id, {
				show_download_link: !selectedFolder.show_download_link
			});
			selectedFolder = updated;
			folderList = folderList.map((f) => (f.id === updated.id ? updated : f));
			showToast(
				updated.show_download_link
					? 'Download link visible to uploaders'
					: 'Download link hidden from uploaders'
			);
		} catch (e) {
			console.error('Failed to toggle download link visibility:', e);
			showToast('Failed to update setting', 'error');
		}
	}

	async function updateStorageLimit() {
		if (!selectedFolder) return;
		try {
			const updated = await folders.update(selectedFolder.id, { storage_limit_gb: selectedFolder.storage_limit_gb });
			selectedFolder = updated;
			folderList = folderList.map((f) => (f.id === updated.id ? updated : f));
			showToast('Storage limit updated');
		} catch (e) {
			console.error('Failed to update storage limit:', e);
			showToast('Failed to update storage limit', 'error');
		}
	}

	async function deleteFolder() {
		if (!selectedFolder) return;
		if (!confirm('Are you sure you want to delete this folder configuration? The Nextcloud folder will not be deleted.')) {
			return;
		}
		const folderId = selectedFolder.id;
		try {
			await folders.delete(selectedFolder.id);
			folderList = folderList.filter((f) => f.id !== folderId);
			showDetailModal = false;
			selectedFolder = null;
			showToast('Folder deleted');
		} catch (e) {
			console.error('Failed to delete folder:', e);
			showToast('Failed to delete folder', 'error');
		}
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
		showToast('Copied to clipboard');
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
	}
</script>

<svelte:head>
	<title>Dashboard - Photo Import Sorter</title>
</svelte:head>

<!-- Toast Notification -->
{#if toast.show}
	<div 
		class="fixed top-4 right-4 z-50"
		transition:fly={{ y: -20, duration: 300 }}
	>
		<div class={`px-4 py-3 rounded-lg shadow-lg flex items-center space-x-3 ${
			toast.type === 'success' 
				? 'bg-green-600 text-white' 
				: 'bg-red-600 text-white'
		}`}>
			{#if toast.type === 'success'}
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
				</svg>
			{:else}
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			{/if}
			<span class="font-medium">{toast.message}</span>
		</div>
	</div>
{/if}

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
	<div class="flex justify-between items-center mb-8">
		<h1 class="text-3xl font-bold text-gray-900">My Folders</h1>
		<button class="btn btn-primary" on:click={() => (showCreateModal = true)}>
			<svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
			</svg>
			New Folder
		</button>
	</div>

	{#if loading}
		<div class="text-center py-12">
			<div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
			<p class="mt-2 text-gray-600">Loading folders...</p>
		</div>
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
			{error}
		</div>
	{:else if folderList.length === 0}
		<div class="text-center py-12 bg-white rounded-xl shadow-lg">
			<svg class="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
			</svg>
			<h3 class="text-lg font-semibold text-gray-900 mb-2">No folders yet</h3>
			<p class="text-gray-600 mb-4">Create your first folder to start collecting photos.</p>
			<button class="btn btn-primary" on:click={() => (showCreateModal = true)}>Create Folder</button>
		</div>
	{:else}
		<div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
			{#each folderList as folder}
				<div class="card hover:shadow-xl transition-shadow cursor-pointer" on:click={() => openDetail(folder)} on:keypress={(e) => e.key === 'Enter' && openDetail(folder)} role="button" tabindex="0">
					<div class="flex justify-between items-start mb-4">
						<h3 class="text-lg font-semibold text-gray-900">{folder.name}</h3>
						<span class={`px-2 py-1 rounded-full text-xs font-medium ${folder.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
							{folder.is_active ? 'Active' : 'Paused'}
						</span>
					</div>
					<p class="text-gray-600 text-sm mb-2">Event: {folder.event_name}</p>
					<p class="text-gray-500 text-xs mb-4 truncate">{folder.nextcloud_folder_path}</p>
					<div class="flex justify-between text-sm">
						<span class="text-gray-500">{folder.upload_count || 0} uploads</span>
						<span class="text-primary-600 hover:text-primary-700">View details →</span>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<!-- Create Modal -->
{#if showCreateModal}
	<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
		<div class="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
			<div class="p-6">
				<div class="flex justify-between items-center mb-6">
					<h2 class="text-2xl font-bold">Create New Folder</h2>
					<button class="text-gray-400 hover:text-gray-600" on:click={() => (showCreateModal = false)}>
						<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>

				{#if createError}
					<div class="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-red-700 text-sm">
						{createError}
					</div>
				{/if}

				<form on:submit|preventDefault={createFolder}>
					<div class="space-y-4">
						<div>
							<label class="label" for="name">Folder Name</label>
							<input type="text" id="name" class="input" bind:value={createForm.name} placeholder="Wedding Photos 2026" required />
						</div>

						<div>
							<label class="label" for="event_name">Event Name (for filenames)</label>
							<input type="text" id="event_name" class="input" bind:value={createForm.event_name} placeholder="wedding" required />
							<p class="text-xs text-gray-500 mt-1">Used in generated filenames, e.g., 2026-01-12_wedding.jpg</p>
						</div>

						<div>
							<label class="label" for="nextcloud_path">Nextcloud Folder Path</label>
							<input type="text" id="nextcloud_path" class="input" bind:value={createForm.nextcloud_folder_path} placeholder="Photos/Wedding2026" required />
							<p class="text-xs text-gray-500 mt-1">Path relative to your Nextcloud root. Will be created if it doesn't exist.</p>
						</div>

						<div>
							<label class="label" for="naming_format">Naming Format</label>
							<select id="naming_format" class="input" bind:value={createForm.naming_format}>
								{#each namingFormats as format}
									<option value={format.value}>{format.label}</option>
								{/each}
							</select>
						</div>

						<div>
							<label class="label" for="jpeg_quality">JPEG Quality ({createForm.jpeg_quality})</label>
							<input type="range" id="jpeg_quality" min="60" max="100" class="w-full" bind:value={createForm.jpeg_quality} />
							<div class="flex justify-between text-xs text-gray-500">
								<span>Smaller files</span>
								<span>Better quality</span>
							</div>
						</div>

						<div>
							<label class="label" for="readme_message">README Message (optional)</label>
							<textarea id="readme_message" class="input" rows="3" bind:value={createForm.readme_message} placeholder="Welcome! Thanks for sharing your photos..."></textarea>
						</div>

						<div>
							<label class="label" for="storage_limit">Storage Limit (GB, optional)</label>
							<input type="number" id="storage_limit" class="input" bind:value={createForm.storage_limit_gb} placeholder="e.g., 5 for 5GB" min="0.1" step="0.1" />
							<p class="text-xs text-gray-500 mt-1">Maximum storage allowed for this folder. Leave empty for no limit.</p>
						</div>

						<div class="flex items-start gap-3 pt-1">
							<input
								type="checkbox"
								id="show_download_link"
								class="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
								bind:checked={createForm.show_download_link}
							/>
							<div>
								<label class="font-medium text-sm text-gray-900" for="show_download_link">
									Share download link with uploaders
								</label>
								<p class="text-xs text-gray-500 mt-0.5">
									When disabled, uploaders can only upload files and won't see the shared Nextcloud folder link.
								</p>
							</div>
						</div>
					</div>

					<div class="flex justify-end space-x-3 mt-6">
						<button type="button" class="btn btn-secondary" on:click={() => (showCreateModal = false)}>Cancel</button>
						<button type="submit" class="btn btn-primary" disabled={creating}>
							{creating ? 'Creating...' : 'Create Folder'}
						</button>
					</div>
				</form>
			</div>
		</div>
	</div>
{/if}

<!-- Detail Modal -->
{#if showDetailModal && selectedFolder}
	<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
		<div class="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
			<div class="p-6">
				<div class="flex justify-between items-center mb-6">
					<h2 class="text-2xl font-bold">{selectedFolder.name}</h2>
					<button class="text-gray-400 hover:text-gray-600" on:click={() => (showDetailModal = false)}>
						<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>

				<div class="space-y-6">
					<!-- Status -->
					<div class="flex items-center justify-between bg-gray-50 rounded-lg p-4">
						<div>
							<p class="font-medium">Upload Status</p>
							<p class="text-sm text-gray-600">{selectedFolder.is_active ? 'Accepting uploads' : 'Uploads paused'}</p>
						</div>
						<button class={`btn ${selectedFolder.is_active ? 'btn-secondary' : 'btn-primary'}`} on:click={toggleActive}>
							{selectedFolder.is_active ? 'Pause' : 'Enable'}
						</button>
					</div>

					<!-- Share Download Link with Uploaders -->
					<div class="flex items-center justify-between bg-gray-50 rounded-lg p-4">
						<div>
							<p class="font-medium">Share Download Link with Uploaders</p>
							<p class="text-sm text-gray-600">
								{selectedFolder.show_download_link
									? 'Uploaders can view & download from the shared folder'
									: 'Upload-only mode (download link hidden from uploaders)'}
							</p>
						</div>
						<button
							class={`btn ${selectedFolder.show_download_link ? 'btn-secondary' : 'btn-primary'}`}
							on:click={toggleShowDownloadLink}
						>
							{selectedFolder.show_download_link ? 'Disable' : 'Enable'}
						</button>
					</div>

					<!-- Upload Link -->
					<div class="bg-primary-50 rounded-lg p-4">
						<p class="font-medium text-primary-900 mb-2">Upload Link (share this)</p>
						<div class="flex items-center space-x-2">
							<input type="text" readonly class="input text-sm flex-1" value={selectedFolder.upload_url} />
							<button class="btn btn-primary" on:click={() => copyToClipboard(selectedFolder?.upload_url ?? '')}>Copy</button>
						</div>
						<button class="text-sm text-primary-700 hover:text-primary-800 mt-2" on:click={regenerateUploadToken}>
							Regenerate link (invalidates old one)
						</button>
					</div>

					<!-- Nextcloud Share Link -->
					{#if selectedFolder.nextcloud_share_url}
						<div class="bg-green-50 rounded-lg p-4">
							<p class="font-medium text-green-900 mb-2">Nextcloud Download Link</p>
							<div class="flex items-center space-x-2">
								<input type="text" readonly class="input text-sm flex-1" value={selectedFolder.nextcloud_share_url} />
								<button class="btn btn-primary" on:click={() => copyToClipboard(selectedFolder?.nextcloud_share_url ?? '')}>Copy</button>
							</div>
							<button class="text-sm text-green-700 hover:text-green-800 mt-2" on:click={regenerateNextcloudShare}>
								Regenerate share link
							</button>
						</div>
					{/if}

					<!-- Details -->
					<div class="grid grid-cols-2 gap-4">
						<div>
							<p class="text-sm text-gray-500">Event Name</p>
							<p class="font-medium">{selectedFolder.event_name}</p>
						</div>
						<div>
							<p class="text-sm text-gray-500">Nextcloud Path</p>
							<p class="font-medium">{selectedFolder.nextcloud_folder_path}</p>
						</div>
						<div>
							<p class="text-sm text-gray-500">Naming Format</p>
							<p class="font-medium">{selectedFolder.naming_format}</p>
						</div>
						<div>
							<p class="text-sm text-gray-500">JPEG Quality</p>
							<p class="font-medium">{selectedFolder.jpeg_quality}%</p>
						</div>
					</div>

					<!-- Storage Limit (editable) -->
					<div class="bg-gray-50 rounded-lg p-4">
						<div class="flex items-center justify-between">
							<div class="flex-1">
								<p class="font-medium">Storage Limit</p>
								<div class="flex items-center space-x-2 mt-2">
									<input type="number" class="input w-48" bind:value={selectedFolder.storage_limit_gb} placeholder="No limit" min="0.1" step="0.1" />
									<span class="text-sm text-gray-600">GB</span>
									<button class="btn btn-primary btn-sm" on:click={updateStorageLimit}>Save</button>
								</div>
								<p class="text-xs text-gray-500 mt-1">Leave empty for no limit</p>
							</div>
						</div>
					</div>

					<!-- Statistics Link -->
					<a href="{base}/dashboard/folder/{selectedFolder.id}/statistics" class="block bg-gray-50 rounded-lg p-4 hover:bg-gray-100 transition-colors">
						<div class="flex justify-between items-center">
							<div>
								<p class="font-medium">View Statistics</p>
								<p class="text-sm text-gray-600">See upload history and analytics</p>
							</div>
							<svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
							</svg>
						</div>
					</a>

					<!-- Danger Zone -->
					<div class="border-t pt-6">
						<h3 class="text-red-600 font-medium mb-3">Danger Zone</h3>
						<button class="btn btn-danger" on:click={deleteFolder}>Delete Folder Configuration</button>
						<p class="text-xs text-gray-500 mt-2">This only removes the configuration. Your Nextcloud folder and files will remain.</p>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}

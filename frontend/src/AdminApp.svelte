<script lang="ts">
	import { folders, type PhotoFolder, type NamingFormat } from './lib/api';
	import { onMount } from 'svelte';
	import { fly } from 'svelte/transition';
	import FolderStatistics from './FolderStatistics.svelte';

	let folderList: PhotoFolder[] = [];
	let namingFormats: NamingFormat[] = [];
	let loading = true;
	let error = '';

	let searchQuery = '';
	let selectedYear = 'all';

	$: years = Array.from(
		new Set(
			folderList.map(f => {
				const date = new Date(f.created_at);
				return isNaN(date.getTime()) ? null : date.getFullYear().toString();
			}).filter((y): y is string => y !== null)
		)
	).sort((a, b) => b.localeCompare(a));

	$: filteredFolders = folderList.filter(f => {
		const matchesSearch = searchQuery === '' || 
			f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
			f.event_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
			f.nextcloud_folder_path.toLowerCase().includes(searchQuery.toLowerCase());
		
		let matchesYear = true;
		if (selectedYear !== 'all') {
			const date = new Date(f.created_at);
			const year = isNaN(date.getTime()) ? null : date.getFullYear().toString();
			matchesYear = year === selectedYear;
		}
		
		return matchesSearch && matchesYear;
	});

	// View state
	let currentView: 'dashboard' | 'statistics' = 'dashboard';
	let currentFolderId: number | null = null;

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
		naming_format: 'DATE_EVENT',
		jpeg_quality: 90,
		video_crf: 23,
		readme_message: ''
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
			showToast('Folder configuration created');
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
			naming_format: 'DATE_EVENT',
			jpeg_quality: 90,
			video_crf: 23,
			readme_message: ''
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
</script>

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

<div class="relative min-h-screen w-full overflow-hidden text-left pb-12">
	<!-- Ambient Background Orbs -->
	<div class="absolute top-0 left-0 w-full h-full pointer-events-none overflow-hidden z-0">
		<div class="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-indigo-500 opacity-[0.05] blur-[120px]"></div>
		<div class="absolute top-1/3 right-10 w-96 h-96 rounded-full bg-cyan-500 opacity-[0.04] blur-[120px]"></div>
		<div class="absolute bottom-10 left-1/3 w-96 h-96 rounded-full bg-purple-500 opacity-[0.03] blur-[120px]"></div>
	</div>

	<div class="relative z-10">
		{#if currentView === 'statistics' && currentFolderId !== null}
			<FolderStatistics folderId={currentFolderId} on:back={() => currentView = 'dashboard'} />
		{:else}
			<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
				<div class="flex justify-between items-center mb-8">
					<h1 class="text-3xl font-extrabold tracking-tight text-gray-900">
						<span class="gps-title-gradient" style="color: var(--color-primary, #0082c9) !important;">Group Photo Sorter</span>
					</h1>
					<button class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg flex items-center shadow border-none cursor-pointer" on:click={() => (showCreateModal = true)} style="background-color: var(--color-primary, #0082c9) !important; color: var(--color-primary-text, #ffffff) !important;">
						<svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
						</svg>
						New Folder Link
					</button>
				</div>

				{#if loading}
					<div class="text-center py-12">
						<div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent"></div>
						<p class="mt-2 text-gray-600">Loading folder configurations...</p>
					</div>
				{:else if error}
					<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
						{error}
					</div>
				{:else if folderList.length === 0}
					<div class="text-center py-12 bg-white rounded-xl shadow border border-gray-100">
						<svg class="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
						</svg>
						<h3 class="text-lg font-semibold text-gray-900 mb-2">No folder configurations yet</h3>
						<p class="text-gray-600 mb-4">Create a folder sorting config to get a shareable upload link for guests.</p>
						<button class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg border-none cursor-pointer" on:click={() => (showCreateModal = true)} style="background-color: var(--color-primary, #0082c9) !important; color: var(--color-primary-text, #ffffff) !important;">Create Folder Link</button>
					</div>
				{:else}
					<!-- Search and Filter Bar -->
					<div class="bg-white rounded-xl shadow p-4 mb-6 border border-gray-100 flex flex-col sm:flex-row gap-4 items-center justify-between">
						<div class="relative w-full sm:max-w-md">
							<input
								type="text"
								placeholder="Search by folder name, event, or path..."
								bind:value={searchQuery}
								class="w-full pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
							/>
						</div>
						
						<div class="flex items-center gap-2 w-full sm:w-auto justify-end">
							<span class="text-sm font-medium text-gray-600">Year:</span>
							<select
								bind:value={selectedYear}
								class="py-2 pl-3 pr-8 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm bg-white"
							>
								<option value="all">All Years</option>
								{#each years as y}
									<option value={y}>{y}</option>
								{/each}
							</select>
						</div>
					</div>

					{#if filteredFolders.length === 0}
						<div class="text-center py-12 bg-white rounded-xl shadow border border-gray-100">
							<svg class="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
							</svg>
							<h3 class="text-lg font-semibold text-gray-900 mb-2">No matching folder configurations found</h3>
							<p class="text-gray-600">Try adjusting your search query or year filter.</p>
						</div>
					{:else}
						<div class="flex flex-wrap justify-start gap-6">
							{#each filteredFolders as folder}
								<div class="gps-folder-card bg-white rounded-xl shadow p-6 border border-gray-100 hover:shadow-md transition-shadow cursor-pointer text-left" on:click={() => openDetail(folder)} on:keypress={(e) => e.key === 'Enter' && openDetail(folder)} role="button" tabindex="0">
									<div class="flex justify-between items-start mb-4">
										<h3 class="text-lg font-semibold text-gray-900 truncate max-w-[180px]">{folder.name}</h3>
										<span class={`px-2 py-0.5 rounded-full text-xs font-medium ${folder.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
											{folder.is_active ? 'Active' : 'Paused'}
										</span>
									</div>
									<p class="text-gray-600 text-sm mb-1">Event: <strong class="text-gray-800">{folder.event_name}</strong></p>
									<p class="text-gray-500 text-xs mb-4 truncate" title={folder.nextcloud_folder_path}>{folder.nextcloud_folder_path}</p>
									<div class="flex justify-between text-sm pt-2 border-t border-gray-50">
										<span class="text-gray-500">{folder.upload_count || 0} uploads</span>
										<span class="text-blue-600 hover:text-blue-700 font-semibold">View details →</span>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				{/if}
			</div>
		{/if}
	</div>
</div>

<!-- Create Modal -->
{#if showCreateModal}
	<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
		<div class="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
			<div class="p-6 text-left">
				<div class="flex justify-between items-center mb-6">
					<h2 class="text-2xl font-bold text-gray-900">Create New Folder Link</h2>
					<button class="text-gray-400 hover:text-gray-600 bg-none border-none cursor-pointer" on:click={() => (showCreateModal = false)}>
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
							<label class="block text-sm font-semibold text-gray-700 mb-1" for="name">Folder Display Name</label>
							<input type="text" id="name" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" bind:value={createForm.name} placeholder="Wedding Photos 2026" required />
						</div>

						<div>
							<label class="block text-sm font-semibold text-gray-700 mb-1" for="event_name">Event Name (for filenames)</label>
							<input type="text" id="event_name" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" bind:value={createForm.event_name} placeholder="wedding" required />
							<p class="text-xs text-gray-500 mt-1">Used in generated filenames, e.g., 2026-01-12_143052_wedding.jpg</p>
						</div>

						<div>
							<label class="block text-sm font-semibold text-gray-700 mb-1" for="nextcloud_path">Nextcloud Folder Path</label>
							<input type="text" id="nextcloud_path" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" bind:value={createForm.nextcloud_folder_path} placeholder="Photos/Wedding2026" required />
							<p class="text-xs text-gray-500 mt-1">Path relative to your Nextcloud root. Will be created automatically if missing.</p>
						</div>

						<div>
							<label class="block text-sm font-semibold text-gray-700 mb-1" for="naming_format">Naming Format</label>
							<select id="naming_format" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white" bind:value={createForm.naming_format}>
								{#each namingFormats as format}
									<option value={format.value}>{format.label}</option>
								{/each}
							</select>
						</div>

						<div>
							<label class="block text-sm font-semibold text-gray-700 mb-1" for="jpeg_quality">JPEG Quality ({createForm.jpeg_quality}%)</label>
							<input type="range" id="jpeg_quality" min="60" max="100" class="w-full" bind:value={createForm.jpeg_quality} />
							<div class="flex justify-between text-xs text-gray-500">
								<span>Smaller Files (60%)</span>
								<span>Best Quality (100%)</span>
							</div>
						</div>

						<div>
							<label class="block text-sm font-semibold text-gray-700 mb-1" for="video_crf">Video CRF Quality ({createForm.video_crf})</label>
							<input type="range" id="video_crf" min="18" max="28" class="w-full" bind:value={createForm.video_crf} />
							<div class="flex justify-between text-xs text-gray-500">
								<span>High Quality (CRF 18)</span>
								<span>High Compression (CRF 28)</span>
							</div>
							<p class="text-xs text-gray-500 mt-1">Lower values mean better quality but larger files. CRF 23 is recommended.</p>
						</div>

						<div>
							<label class="block text-sm font-semibold text-gray-700 mb-1" for="readme_message">README Message for Upload Page (optional)</label>
							<textarea id="readme_message" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" rows="3" bind:value={createForm.readme_message} placeholder="Welcome! Thanks for sharing your photos with us..."></textarea>
						</div>
					</div>

					<div class="flex justify-end space-x-3 mt-6">
						<button type="button" class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 bg-white cursor-pointer" on:click={() => (showCreateModal = false)}>Cancel</button>
						<button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold border-none cursor-pointer" disabled={creating} style="background-color: var(--color-primary, #0082c9) !important; color: var(--color-primary-text, #ffffff) !important;">
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
			<div class="p-6 text-left">
				<div class="flex justify-between items-center mb-6">
					<h2 class="text-2xl font-bold text-gray-900">{selectedFolder.name}</h2>
					<button class="text-gray-400 hover:text-gray-600 bg-none border-none cursor-pointer" on:click={() => (showDetailModal = false)}>
						<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>

				<div class="space-y-6">
					<!-- Status -->
					<div class="flex items-center justify-between bg-gray-50 rounded-lg p-4">
						<div>
							<p class="font-semibold text-gray-800">Upload Link Status</p>
							<p class="text-sm text-gray-600">{selectedFolder.is_active ? 'Accepting uploads' : 'Uploads paused'}</p>
						</div>
						<button class={`px-4 py-2 rounded-lg font-semibold border-none cursor-pointer ${selectedFolder.is_active ? 'bg-gray-200 hover:bg-gray-300 text-gray-800' : 'bg-blue-600 hover:bg-blue-700 text-white'}`} on:click={toggleActive} style={selectedFolder.is_active ? '' : 'background-color: var(--color-primary, #0082c9) !important; color: var(--color-primary-text, #ffffff) !important;'}>
							{selectedFolder.is_active ? 'Pause Link' : 'Enable Link'}
						</button>
					</div>

					<!-- Upload Link -->
					<div class="bg-blue-50 rounded-lg p-4 border border-blue-100">
						<p class="font-semibold text-blue-900 mb-2">Guest Upload URL (share this link with uploaders)</p>
						<div class="flex items-center space-x-2">
							<input type="text" readonly class="w-full px-3 py-2 border border-blue-200 bg-white rounded-lg text-sm focus:outline-none" value={selectedFolder.upload_url} />
							<button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold border-none cursor-pointer" on:click={() => copyToClipboard(selectedFolder?.upload_url ?? '')} style="background-color: var(--color-primary, #0082c9) !important; color: var(--color-primary-text, #ffffff) !important;">Copy</button>
						</div>
						<button class="text-sm text-blue-700 hover:text-blue-855 mt-2 bg-transparent border-none cursor-pointer p-0 underline" on:click={regenerateUploadToken}>
							Regenerate link (invalidates old URL)
						</button>
					</div>

					<!-- Nextcloud Share Link -->
					{#if selectedFolder.nextcloud_share_token}
						<div class="bg-green-50 rounded-lg p-4 border border-green-100">
							<p class="font-semibold text-green-900 mb-2">Nextcloud View/Download Link</p>
							<div class="flex items-center space-x-2">
								<input type="text" readonly class="w-full px-3 py-2 border border-green-200 bg-white rounded-lg text-sm focus:outline-none" value={selectedFolder.nextcloud_share_url} />
								<button class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold border-none cursor-pointer" on:click={() => copyToClipboard(selectedFolder?.nextcloud_share_url ?? '')}>Copy</button>
							</div>
							<button class="text-sm text-green-700 hover:text-green-800 mt-2 bg-transparent border-none cursor-pointer p-0 underline" on:click={regenerateNextcloudShare}>
								Regenerate share link
							</button>
						</div>
					{/if}

					<!-- Details -->
					<div class="grid grid-cols-2 gap-4">
						<div>
							<p class="text-sm text-gray-500">Event Tag</p>
							<p class="font-semibold text-gray-800">{selectedFolder.event_name}</p>
						</div>
						<div>
							<p class="text-sm text-gray-500">Nextcloud Path</p>
							<p class="font-semibold text-gray-800 truncate" title={selectedFolder.nextcloud_folder_path}>{selectedFolder.nextcloud_folder_path}</p>
						</div>
						<div>
							<p class="text-sm text-gray-500">Naming Format</p>
							<p class="font-semibold text-gray-800">{selectedFolder.naming_format}</p>
						</div>
						<div>
							<p class="text-sm text-gray-500">JPEG Quality</p>
							<p class="font-semibold text-gray-800">{selectedFolder.jpeg_quality}%</p>
						</div>
					</div>

					<!-- Statistics Link -->
					<button on:click={() => { currentView = 'statistics'; currentFolderId = selectedFolder.id; showDetailModal = false; }} class="w-full text-left bg-gray-50 rounded-lg p-4 hover:bg-gray-100 transition-colors border-none cursor-pointer">
						<div class="flex justify-between items-center">
							<div>
								<p class="font-semibold text-gray-800">View Link Statistics</p>
								<p class="text-sm text-gray-600">See upload history, file counts, sizes, and savings</p>
							</div>
							<svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
							</svg>
						</div>
					</button>

					<!-- Danger Zone -->
					<div class="border-t border-gray-100 pt-6">
						<h3 class="text-red-600 font-semibold mb-3">Danger Zone</h3>
						<button class="bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-4 rounded-lg border-none cursor-pointer" on:click={deleteFolder}>Delete Configuration</button>
						<p class="text-xs text-gray-500 mt-2">This only deletes the settings link. Your files and folders in Nextcloud will NOT be affected.</p>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}

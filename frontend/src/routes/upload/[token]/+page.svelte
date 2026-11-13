<script lang="ts">
	import { page } from '$app/stores';
	import { upload, type FolderInfo } from '$lib/api';
	import { onMount } from 'svelte';

	interface FileUpload {
		file: File;
		id: string; // Stable ID for keying
		status: 'pending' | 'uploading' | 'processing' | 'success' | 'error';
		progress: number;
		taskId?: string;
		error?: string;
		result?: {
			filename: string;
			original_size: number;
			converted_size: number;
		};
	}

	// Session management - persist upload session for 7 days
	const SESSION_COOKIE_NAME = 'photo_upload_session';
	const SESSION_DURATION_DAYS = 7;
	const MAX_CONCURRENT_UPLOADS = 3;

	let folderInfo: FolderInfo | null = null;
	let loading = true;
	let error = '';

	let files: FileUpload[] = [];
	let isDragOver = false;
	let fileInput: HTMLInputElement;
	let showCompletedFiles = true;
	let sessionId: string | null = null;
	let filterStatus: 'all' | 'active' | 'success' | 'error' = 'all';
	let searchQuery = '';
	let uploadIdCounter = 0;

	// Generate stable ID for file uploads
	function generateUploadId(): string {
		return `upload_${Date.now()}_${++uploadIdCounter}`;
	}

	function normalizeExt(ext: string): string {
		const lower = ext.trim().toLowerCase();
		return lower.startsWith('.') ? lower : `.${lower}`;
	}

	// Get shareToken directly from page store to avoid timing issues
	$: shareToken = $page.params.token || '';
	$: allFormats = folderInfo
		? [
				...folderInfo.supported_image_formats.map(normalizeExt),
				...folderInfo.supported_video_formats.map(normalizeExt)
			]
		: [];
	$: acceptString = allFormats.join(',');

	$: uploadComplete =
		files.length > 0 &&
		files.every((f) => f.status === 'success' || f.status === 'error');
	$: successCount = files.filter((f) => f.status === 'success').length;
	$: errorCount = files.filter((f) => f.status === 'error').length;
	$: activeFiles = files.filter((f) => f.status !== 'success' && f.status !== 'error');
	$: completedFiles = files.filter((f) => f.status === 'success' || f.status === 'error');
	$: hasCompletedFiles = completedFiles.length > 0;

	// Filtered files based on status and search
	$: filteredActiveFiles = activeFiles.filter((f) => {
		const matchesSearch =
			searchQuery === '' || f.file.name.toLowerCase().includes(searchQuery.toLowerCase());
		const matchesFilter = filterStatus === 'all' || filterStatus === 'active';
		return matchesSearch && matchesFilter;
	});
	$: filteredCompletedFiles = completedFiles.filter((f) => {
		const matchesSearch =
			searchQuery === '' || f.file.name.toLowerCase().includes(searchQuery.toLowerCase());
		const matchesFilter =
			filterStatus === 'all' ||
			(filterStatus === 'success' && f.status === 'success') ||
			(filterStatus === 'error' && f.status === 'error');
		return matchesSearch && matchesFilter;
	});

	// Session cookie helpers
	function getSessionId(token: string): string | null {
		const cookies = document.cookie.split(';');
		for (const cookie of cookies) {
			const [name, value] = cookie.trim().split('=');
			if (name === `${SESSION_COOKIE_NAME}_${token}`) {
				return value;
			}
		}
		return null;
	}

	function setSessionId(token: string, id: string) {
		const expires = new Date();
		expires.setDate(expires.getDate() + SESSION_DURATION_DAYS);
		document.cookie = `${SESSION_COOKIE_NAME}_${token}=${id}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
	}

	function generateSessionId(): string {
		if (typeof crypto !== 'undefined' && crypto.randomUUID) {
			try {
				return crypto.randomUUID();
			} catch {
				// Fall through to getRandomValues fallback
			}
		}
		if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
			const bytes = new Uint8Array(16);
			crypto.getRandomValues(bytes);
			bytes[6] = (bytes[6] & 0x0f) | 0x40;
			bytes[8] = (bytes[8] & 0x3f) | 0x80;
			const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
			return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
		}
		return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
	}

	// Persist file state to localStorage
	function saveSessionState() {
		if (!sessionId) return;
		const state = files.map((f) => ({
			id: f.id,
			name: f.file.name,
			size: f.file.size,
			status: f.status,
			taskId: f.taskId,
			error: f.error,
			result: f.result
		}));
		localStorage.setItem(`upload_session_${shareToken}_${sessionId}`, JSON.stringify(state));
	}

	function loadSessionState(
		token: string
	): {
		id?: string;
		name: string;
		size: number;
		status: string;
		taskId?: string;
		error?: string;
		result?: any;
	}[] | null {
		if (!sessionId) return null;
		const stored = localStorage.getItem(`upload_session_${token}_${sessionId}`);
		if (!stored) return null;
		try {
			return JSON.parse(stored);
		} catch {
			return null;
		}
	}

	onMount(async () => {
		const token = $page.params.token || '';

		try {
			sessionId = getSessionId(token);
			if (!sessionId) {
				sessionId = generateSessionId();
				setSessionId(token, sessionId);
			}
		} catch (e) {
			console.warn('Failed to initialize session:', e);
			sessionId = null;
		}

		await loadFolderInfo();

		// Restore session if exists (prefer server Redis session, fallback to localStorage)
		try {
			let savedState = null;
			if (sessionId) {
				try {
					const res = await upload.sessionStatus(token, sessionId);
					if (res && Array.isArray(res.files) && res.files.length > 0) {
						savedState = res.files.map((item) => ({
							id: item.taskId,
							name: item.name,
							size: item.size,
							status: String(item.status || 'pending').toLowerCase(),
							taskId: item.taskId,
							error: item.error,
							result: item.result
						}));
					}
				} catch {
					// Fallback to localStorage below
				}
			}

			if (!savedState) {
				savedState = loadSessionState(token);
			}

			if (savedState && savedState.length > 0) {
				for (const item of savedState) {
					const itemId = item.id || generateUploadId();
					const normalizedStatus =
						item.status === 'started'
							? 'processing'
							: item.status === 'failure'
								? 'error'
								: item.status;

					if (normalizedStatus === 'success' || normalizedStatus === 'error') {
						const placeholderFile = new File([], item.name, {
							type: 'application/octet-stream'
						});
						Object.defineProperty(placeholderFile, 'size', { value: item.size });

						files = [
							...files,
							{
								id: itemId,
								file: placeholderFile,
								status: normalizedStatus as FileUpload['status'],
								progress: normalizedStatus === 'success' ? 100 : 0,
								taskId: item.taskId,
								error: item.error,
								result: item.result
							}
						];
					} else if (
						item.taskId &&
						(normalizedStatus === 'processing' ||
							normalizedStatus === 'uploading' ||
							normalizedStatus === 'pending' ||
							normalizedStatus === 'retry')
					) {
						const placeholderFile = new File([], item.name, {
							type: 'application/octet-stream'
						});
						Object.defineProperty(placeholderFile, 'size', { value: item.size });

						const fileUpload: FileUpload = {
							id: itemId,
							file: placeholderFile,
							status: 'processing',
							progress: 50,
							taskId: item.taskId
						};
						files = [...files, fileUpload];

						pollTaskStatusById(itemId, item.taskId);
					}
				}

				if (activeFiles.length > 0 && completedFiles.length > 0) {
					showCompletedFiles = false;
				}
			}
		} catch (e) {
			console.warn('Failed to restore session state:', e);
		}
	});

	async function loadFolderInfo() {
		loading = true;
		error = '';
		try {
			folderInfo = await upload.folderInfo(shareToken);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load folder info';
		} finally {
			loading = false;
		}
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		isDragOver = true;
	}

	function handleDragLeave(e: DragEvent) {
		e.preventDefault();
		isDragOver = false;
	}

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		isDragOver = false;

		if (e.dataTransfer?.files) {
			addFiles(Array.from(e.dataTransfer.files));
		}
	}

	function handleFileSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		if (input.files && input.files.length > 0) {
			addFiles(Array.from(input.files));
			input.value = '';
		}
	}

	function addFiles(newFiles: File[]) {
		if (!folderInfo || allFormats.length === 0) {
			alert('Please wait for the page to finish loading before uploading files.');
			return;
		}

		const validFiles = newFiles.filter((file) => {
			const ext = '.' + (file.name.split('.').pop()?.toLowerCase() || '');
			const isValid = allFormats.includes(ext);
			if (!isValid) {
				console.log(`Rejected file ${file.name}: extension ${ext} not in ${allFormats.join(', ')}`);
			}
			return isValid;
		});

		if (validFiles.length === 0 && newFiles.length > 0) {
			const exts = newFiles.map((f) => '.' + f.name.split('.').pop()?.toLowerCase()).join(', ');
			alert(
				`No valid files found. Supported formats: ${allFormats.join(', ')}\nYour files: ${exts}`
			);
			return;
		}

		const oversizedFiles = validFiles.filter(
			(file) => file.size > (folderInfo?.max_upload_size_mb || 5120) * 1024 * 1024
		);

		if (oversizedFiles.length > 0) {
			alert(
				`Some files are too large (max ${folderInfo?.max_upload_size_mb}MB): ${oversizedFiles.map((f) => f.name).join(', ')}`
			);
		}

		const okFiles = validFiles.filter(
			(file) => file.size <= (folderInfo?.max_upload_size_mb || 5120) * 1024 * 1024
		);

		const newUploads: FileUpload[] = okFiles.map((file) => ({
			id: generateUploadId(),
			file,
			status: 'pending',
			progress: 0
		}));

		files = [...files, ...newUploads];
		processUploadQueue();
	}

	function findFileIndex(id: string): number {
		return files.findIndex((f) => f.id === id);
	}

	function updateFile(id: string, updates: Partial<FileUpload>) {
		const index = findFileIndex(id);
		if (index === -1) return;
		files[index] = { ...files[index], ...updates };
		files = files;
	}

	function processUploadQueue() {
		const uploadingCount = files.filter((f) => f.status === 'uploading').length;
		if (uploadingCount >= MAX_CONCURRENT_UPLOADS) {
			return;
		}

		const pendingFiles = files.filter((f) => f.status === 'pending');
		const vacancies = MAX_CONCURRENT_UPLOADS - uploadingCount;
		const filesToStart = pendingFiles.slice(0, vacancies);

		filesToStart.forEach((f) => {
			uploadFileById(f.id);
		});
	}

	async function uploadFileById(id: string) {
		const index = findFileIndex(id);
		if (index === -1) return;

		const fileUpload = files[index];
		if (fileUpload.status !== 'pending' && fileUpload.status !== 'uploading') return;

		updateFile(id, { status: 'uploading', progress: 10 });
		saveSessionState();

		try {
			const result = await upload.uploadFile(shareToken, fileUpload.file, sessionId);
			updateFile(id, {
				status: 'processing',
				progress: 50,
				taskId: result.task_id
			});
			saveSessionState();

			processUploadQueue();
			pollTaskStatusById(id, result.task_id);
		} catch (e) {
			updateFile(id, {
				status: 'error',
				error: e instanceof Error ? e.message : 'Upload failed'
			});
			saveSessionState();
			processUploadQueue();
		}
	}

	async function pollTaskStatusById(id: string, taskId: string) {
		let attempts = 0;
		const maxAttempts = 360; // 30 minutes max for large videos
		let lastProgress = 50;

		while (attempts < maxAttempts) {
			const index = findFileIndex(id);
			if (index === -1) return;

			try {
				const status = await upload.taskStatus(taskId);

				if (status.status === 'SUCCESS' && status.result) {
					updateFile(id, {
						status: 'success',
						progress: 100,
						result: status.result
					});
					saveSessionState();
					return;
				} else if (status.status === 'FAILURE') {
					updateFile(id, {
						status: 'error',
						error: status.error || 'Processing failed'
					});
					saveSessionState();
					return;
				}

				const progressEstimate = Math.min(50 + Math.floor(attempts / 2), 95);
				if (progressEstimate !== lastProgress) {
					lastProgress = progressEstimate;
					updateFile(id, { progress: progressEstimate });
				}
			} catch (e) {
				console.error('Failed to check task status:', e);
			}

			attempts++;
			await new Promise((resolve) => setTimeout(resolve, 3000));
		}

		updateFile(id, {
			status: 'error',
			error: 'Processing timed out'
		});
		saveSessionState();
	}

	function removeFileById(id: string) {
		files = files.filter((f) => f.id !== id);
		saveSessionState();
		processUploadQueue();
	}

	function clearCompletedFiles() {
		files = files.filter((f) => f.status !== 'success' && f.status !== 'error');
		saveSessionState();
	}

	function retryFile(id: string) {
		const index = findFileIndex(id);
		if (index === -1) return;

		const fileUpload = files[index];
		if (fileUpload.file.size === 0) {
			alert('Cannot retry this file. Please upload it again.');
			return;
		}

		updateFile(id, {
			status: 'pending',
			progress: 0,
			error: undefined,
			taskId: undefined
		});
		processUploadQueue();
	}

	function retryAllFailed() {
		const failedFiles = files.filter((f) => f.status === 'error' && f.file.size > 0);
		failedFiles.forEach((f) => {
			updateFile(f.id, {
				status: 'pending',
				progress: 0,
				error: undefined,
				taskId: undefined
			});
		});
		processUploadQueue();
	}

	$: retryableErrors = files.filter((f) => f.status === 'error' && f.file.size > 0);
	$: hasRetryableErrors = retryableErrors.length > 0;

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
	}
</script>

<svelte:head>
	<title>{folderInfo?.name || 'Upload'} - Photo Import Sorter</title>
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
	{#if loading}
		<div class="text-center py-12">
			<div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
			<p class="mt-2 text-gray-600">Loading...</p>
		</div>
	{:else if error}
		<div class="card text-center py-12">
			<svg class="w-16 h-16 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
			</svg>
			<h2 class="text-xl font-semibold text-gray-900 mb-2">Folder Not Found</h2>
			<p class="text-gray-600">{error}</p>
		</div>
	{:else if folderInfo}
		<div class="text-center mb-8">
			<h1 class="text-3xl font-bold text-gray-900 mb-2">{folderInfo.name}</h1>
			<p class="text-gray-600">Upload your photos and videos for {folderInfo.event_name}</p>
			{#if folderInfo.readme_message}
				<div class="mt-4 p-4 bg-white rounded-lg text-sm text-gray-700 max-w-xl mx-auto border border-gray-200 whitespace-pre-line text-left shadow-sm">
					{folderInfo.readme_message}
				</div>
			{/if}
		</div>

		<!-- Drop Zone -->
		<label
			class={`block border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer bg-white ${
				isDragOver
					? 'border-primary-500 bg-primary-50'
					: 'border-gray-300 hover:border-gray-400'
			}`}
			on:dragover={handleDragOver}
			on:dragleave={handleDragLeave}
			on:drop={handleDrop}
		>
			<input
				bind:this={fileInput}
				type="file"
				multiple
				accept={acceptString}
				class="sr-only"
				on:change={handleFileSelect}
			/>

			<svg class="w-12 h-12 text-gray-400 mx-auto mb-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
			</svg>

			<p class="text-lg text-gray-700 mb-2 pointer-events-none">
				Drag & drop files here or <span class="text-primary-600 font-medium">browse</span>
			</p>
			<p class="text-sm text-gray-500 pointer-events-none">
				Supports images ({folderInfo.supported_image_formats.join(', ')}) and videos ({folderInfo.supported_video_formats.join(', ')})
			</p>
			<p class="text-xs text-gray-400 mt-2 pointer-events-none">Max file size: {folderInfo.max_upload_size_mb}MB</p>
		</label>

		<!-- File List -->
		{#if files.length > 0}
			<div class="mt-6 space-y-2">
				<!-- Header with filters -->
				<div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-3">
					<div class="flex items-center gap-3">
						<h2 class="text-lg font-semibold">{files.length} file(s)</h2>
						{#if hasCompletedFiles}
							<div class="flex gap-1 text-xs">
								<span class="px-2 py-0.5 rounded-full bg-green-100 text-green-700">{successCount} ✓</span>
								{#if errorCount > 0}
									<span class="px-2 py-0.5 rounded-full bg-red-100 text-red-700">{errorCount} ✗</span>
								{/if}
							</div>
						{/if}
					</div>
					<div class="flex gap-2 items-center flex-wrap">
						<input 
							type="text" 
							placeholder="Search files..." 
							bind:value={searchQuery}
							class="text-sm px-2 py-1 border rounded-md w-32 focus:outline-none focus:ring-1 focus:ring-primary-500"
						/>
						{#if hasCompletedFiles || activeFiles.length > 0}
							<div class="flex text-xs border rounded-md overflow-hidden">
								<button 
									class="px-2 py-1 transition-colors {filterStatus === 'all' ? 'bg-primary-500 text-white' : 'bg-white hover:bg-gray-100'}"
									on:click={() => filterStatus = 'all'}
								>All</button>
								<button 
									class="px-2 py-1 transition-colors {filterStatus === 'active' ? 'bg-blue-500 text-white' : 'bg-white hover:bg-gray-100'}"
									on:click={() => filterStatus = 'active'}
								>⏳</button>
								<button 
									class="px-2 py-1 transition-colors {filterStatus === 'success' ? 'bg-green-500 text-white' : 'bg-white hover:bg-gray-100'}"
									on:click={() => filterStatus = 'success'}
								>✓</button>
								<button 
									class="px-2 py-1 transition-colors {filterStatus === 'error' ? 'bg-red-500 text-white' : 'bg-white hover:bg-gray-100'}"
									on:click={() => filterStatus = 'error'}
								>✗</button>
							</div>
							<button
								class="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
								on:click={() => showCompletedFiles = !showCompletedFiles}
							>
								<svg class="w-3 h-3 transition-transform" class:rotate-180={!showCompletedFiles} fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
								</svg>
								{showCompletedFiles ? 'Hide' : 'Show'}
							</button>
						{/if}
						{#if uploadComplete && successCount > 0 && folderInfo.nextcloud_share_url}
							<a href={folderInfo.nextcloud_share_url} target="_blank" rel="noopener" class="btn btn-primary text-xs py-1 px-2">
								View Photos →
							</a>
						{/if}
					</div>
				</div>

				<!-- Active files (uploading/processing) -->
				{#each filteredActiveFiles as file (file.id)}
					<div class="bg-white rounded-lg shadow-sm p-2 flex items-center gap-3">
						<div class="flex-shrink-0">
							{#if file.status === 'uploading' || file.status === 'processing'}
								<div class="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
							{:else}
								<div class="w-5 h-5 rounded-full bg-gray-200"></div>
							{/if}
						</div>
						<div class="flex-1 min-w-0">
							<p class="text-sm font-medium truncate" title={file.file.name}>{file.file.name}</p>
							<div class="flex items-center gap-2 text-xs text-gray-500">
								<span>{formatBytes(file.file.size)}</span>
								<span>•</span>
								<span>
									{file.status === 'pending'
										? 'Queued...'
										: file.status === 'uploading'
											? 'Uploading...'
											: 'Converting & saving...'}
								</span>
							</div>
						</div>
						<div class="w-16 bg-gray-200 rounded-full h-1.5">
							<div
								class="h-1.5 rounded-full bg-primary-500 transition-all duration-300"
								style="width: {file.progress}%"
							></div>
						</div>
						{#if file.status === 'pending'}
							<button class="text-gray-400 hover:text-gray-600 p-1" on:click={() => removeFileById(file.id)}>
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</button>
						{/if}
					</div>
				{/each}

				<!-- Completed files -->
				{#if showCompletedFiles && filteredCompletedFiles.length > 0}
					<div class="space-y-1 pt-2 border-t">
						<div class="flex items-center justify-between">
							<span class="text-xs text-gray-400">Completed</span>
							<div class="flex gap-2">
								{#if hasRetryableErrors}
									<button 
										class="text-xs text-orange-500 hover:text-orange-700 font-medium"
										on:click={retryAllFailed}
									>
										Retry All Failed ({retryableErrors.length})
									</button>
								{/if}
								<button 
									class="text-xs text-gray-400 hover:text-gray-600"
									on:click={clearCompletedFiles}
								>
									Clear
								</button>
							</div>
						</div>
						{#each filteredCompletedFiles as file (file.id)}
							<div class="bg-white rounded-lg shadow-sm p-2 flex items-center gap-3 opacity-75 hover:opacity-100 transition-opacity">
								<div class="flex-shrink-0">
									{#if file.status === 'success'}
										<svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
										</svg>
									{:else}
										<svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
										</svg>
									{/if}
								</div>
								<div class="flex-1 min-w-0">
									<p class="text-sm truncate" title={file.file.name}>{file.file.name}</p>
									<div class="text-xs text-gray-500">
										{formatBytes(file.file.size)}
										{#if file.result?.converted_size}
											→ {formatBytes(file.result.converted_size)}
										{/if}
										{#if file.result?.filename}
											<span class="text-gray-400 ml-1">({file.result.filename})</span>
										{/if}
										{#if file.error}
											<span class="text-red-500 ml-1">{file.error}</span>
										{/if}
									</div>
								</div>
								{#if file.status === 'error' && file.file.size > 0}
									<button 
										class="text-xs text-orange-500 hover:text-orange-700 px-2 py-1 rounded border border-orange-300 hover:bg-orange-50"
										on:click={() => retryFile(file.id)}
									>
										Retry
									</button>
								{/if}
								<button class="text-gray-400 hover:text-gray-600 p-1" on:click={() => removeFileById(file.id)}>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
									</svg>
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Success Message -->
			{#if uploadComplete && successCount > 0 && folderInfo.nextcloud_share_url}
				<div class="mt-8 bg-green-50 border border-green-200 rounded-xl p-6 text-center">
					<svg class="w-12 h-12 text-green-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					<h3 class="text-xl font-semibold text-green-800 mb-2">
						{successCount} file(s) uploaded successfully!
					</h3>
					<p class="text-green-700 mb-4">
						Your photos and videos have been converted and saved to the shared folder.
					</p>
					<a
						href={folderInfo.nextcloud_share_url}
						target="_blank"
						rel="noopener"
						class="btn btn-primary inline-block"
					>
						View & Download Photos
					</a>
				</div>
			{/if}
		{/if}

		<!-- Info -->
		<div class="mt-8 bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
			<p class="font-medium text-gray-700 mb-2">How it works:</p>
			<ol class="list-decimal list-inside space-y-1">
				<li>Upload your photos and videos</li>
				<li>They'll be automatically converted to JPEG/MP4</li>
				<li>Files are organized and named by capture date</li>
				<li>Click the link above to view and download all photos</li>
			</ol>
		</div>
	{/if}
</div>

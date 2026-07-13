<script lang="ts">
	import { upload, type FolderInfo, type TaskStatus } from './lib/api';
	import { onMount } from 'svelte';
	import { fly } from 'svelte/transition';

	// Receive share token from PHP context
	export let token: string;

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

	let folderInfo: FolderInfo | null = null;
	let loading = true;
	let error = '';

	let files: FileUpload[] = [];
	let isDragOver = false;
	let isWindowDragOver = false;
	let dragCounter = 0;
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

	$: allFormats = folderInfo
		? [...folderInfo.supported_image_formats, ...folderInfo.supported_video_formats]
		: [];
	$: acceptString = allFormats.map((f) => '.' + f).join(',');

	$: uploadComplete =
		files.length > 0 &&
		files.every((f) => f.status === 'success' || f.status === 'error');
	$: successCount = files.filter((f) => f.status === 'success').length;
	$: errorCount = files.filter((f) => f.status === 'error').length;
	$: activeFiles = files.filter((f) => f.status !== 'success' && f.status !== 'error');
	$: completedFiles = files.filter((f) => f.status === 'success' || f.status === 'error');
	$: hasCompletedFiles = completedFiles.length > 0;

	// Filtered files based on status and search
	$: filteredActiveFiles = activeFiles.filter(f => {
		const matchesSearch = searchQuery === '' || f.file.name.toLowerCase().includes(searchQuery.toLowerCase());
		const matchesFilter = filterStatus === 'all' || filterStatus === 'active';
		return matchesSearch && matchesFilter;
	});
	$: filteredCompletedFiles = completedFiles.filter(f => {
		const matchesSearch = searchQuery === '' || f.file.name.toLowerCase().includes(searchQuery.toLowerCase());
		const matchesFilter = filterStatus === 'all' || 
			(filterStatus === 'success' && f.status === 'success') ||
			(filterStatus === 'error' && f.status === 'error');
		return matchesSearch && matchesFilter;
	});

	// Session cookie helpers
	function getSessionId(tok: string): string | null {
		const cookies = document.cookie.split(';');
		for (const cookie of cookies) {
			const [name, value] = cookie.trim().split('=');
			if (name === `${SESSION_COOKIE_NAME}_${tok}`) {
				return value;
			}
		}
		return null;
	}

	function setSessionId(tok: string, id: string) {
		const expires = new Date();
		expires.setDate(expires.getDate() + SESSION_DURATION_DAYS);
		document.cookie = `${SESSION_COOKIE_NAME}_${tok}=${id}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
	}

	function generateSessionId(): string {
		if (typeof crypto !== 'undefined' && crypto.randomUUID) {
			try {
				return crypto.randomUUID();
			} catch {
				// fallback
			}
		}
		if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
			const bytes = new Uint8Array(16);
			crypto.getRandomValues(bytes);
			bytes[6] = (bytes[6] & 0x0f) | 0x40;
			bytes[8] = (bytes[8] & 0x3f) | 0x80;
			const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
			return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
		}
		return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
	}

	// Persist file state to localStorage
	function saveSessionState() {
		if (!sessionId) return;
		const state = files.map(f => ({
			id: f.id,
			name: f.file.name,
			size: f.file.size,
			status: f.status,
			taskId: f.taskId,
			error: f.error,
			result: f.result
		}));
		localStorage.setItem(`upload_session_${token}_${sessionId}`, JSON.stringify(state));
	}

	function loadSessionState(tok: string): any[] | null {
		if (!sessionId) return null;
		const stored = localStorage.getItem(`upload_session_${tok}_${sessionId}`);
		if (!stored) return null;
		try {
			return JSON.parse(stored);
		} catch {
			return null;
		}
	}

	onMount(async () => {
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

		// Restore session if exists
		try {
			let savedState: any[] | null = null;
			if (sessionId) {
				try {
					const res = await upload.sessionStatus(token, sessionId);
					if (res && res.files && res.files.length > 0) {
						savedState = res.files.map(item => ({
							id: item.taskId,
							name: item.name,
							size: item.size,
							status: item.status.toLowerCase(),
							taskId: item.taskId,
							error: item.error,
							result: item.result
						}));
					}
				} catch (err) {
					console.warn('Failed to fetch session from server, falling back to localStorage:', err);
				}
			}

			if (!savedState) {
				savedState = loadSessionState(token);
			}

			if (savedState && savedState.length > 0) {
				for (const item of savedState) {
					const itemId = item.id || generateUploadId();
					const itemStatus = item.status === 'started' ? 'processing' : item.status;
					
					if (itemStatus === 'success' || itemStatus === 'error' || itemStatus === 'failure') {
						const placeholderFile = new File([], item.name, { type: 'application/octet-stream' });
						Object.defineProperty(placeholderFile, 'size', { value: item.size });
						
						files = [...files, {
							id: itemId,
							file: placeholderFile,
							status: (itemStatus === 'failure' ? 'error' : itemStatus) as FileUpload['status'],
							progress: itemStatus === 'success' ? 100 : 0,
							taskId: item.taskId,
							error: item.error,
							result: item.result
						}];
					} else if (item.taskId && (itemStatus === 'processing' || itemStatus === 'uploading' || itemStatus === 'pending')) {
						const placeholderFile = new File([], item.name, { type: 'application/octet-stream' });
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
				
				processUploadQueue();
				
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
			folderInfo = await upload.folderInfo(token);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load event details';
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

	function handleWindowDragEnter(e: DragEvent) {
		e.preventDefault();
		dragCounter++;
		isWindowDragOver = true;
	}

	function handleWindowDragLeave(e: DragEvent) {
		e.preventDefault();
		dragCounter--;
		if (dragCounter <= 0) {
			dragCounter = 0;
			isWindowDragOver = false;
		}
	}

	function handleWindowDrop(e: DragEvent) {
		e.preventDefault();
		dragCounter = 0;
		isWindowDragOver = false;
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
			alert('Please wait for the page to finish loading before uploading.');
			return;
		}

		const validFiles = newFiles.filter((file) => {
			const ext = file.name.split('.').pop()?.toLowerCase();
			return ext && folderInfo?.supported_image_formats.includes(ext) || ext && folderInfo?.supported_video_formats.includes(ext);
		});

		if (validFiles.length === 0 && newFiles.length > 0) {
			alert(`Unsupported file format. Supported formats: ${allFormats.join(', ')}`);
			return;
		}

		const oversizedFiles = validFiles.filter(
			(file) => file.size > (folderInfo?.max_upload_size_mb || 5120) * 1024 * 1024
		);

		if (oversizedFiles.length > 0) {
			alert(`Files too large (max ${folderInfo?.max_upload_size_mb}MB): ${oversizedFiles.map((f) => f.name).join(', ')}`);
			return;
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
		return files.findIndex(f => f.id === id);
	}

	function updateFile(id: string, updates: Partial<FileUpload>) {
		const index = findFileIndex(id);
		if (index === -1) return;
		files[index] = { ...files[index], ...updates };
		files = files;
	}

	const MAX_CONCURRENT_UPLOADS = 3;

	function processUploadQueue() {
		// Count how many files are currently uploading
		const uploadingCount = files.filter(f => f.status === 'uploading').length;
		
		if (uploadingCount >= MAX_CONCURRENT_UPLOADS) {
			return;
		}

		// Find the next pending files
		const pendingFiles = files.filter(f => f.status === 'pending');
		const vacancies = MAX_CONCURRENT_UPLOADS - uploadingCount;
		
		const filesToStart = pendingFiles.slice(0, vacancies);
		filesToStart.forEach(file => {
			uploadFileById(file.id);
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
			const result = await upload.uploadFile(token, fileUpload.file, sessionId);
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
		const maxAttempts = 360; // 30 minutes max for videos
		let lastProgress = 50;

		while (attempts < maxAttempts) {
			const index = findFileIndex(id);
			if (index === -1) return; // File was removed
			
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
						error: status.error || 'Conversion failed'
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
			await new Promise((resolve) => setTimeout(resolve, 5000));
		}

		updateFile(id, {
			status: 'error',
			error: 'Processing timed out'
		});
		saveSessionState();
	}

	function removeFileById(id: string) {
		files = files.filter(f => f.id !== id);
		saveSessionState();
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
		const failedFiles = files.filter(f => f.status === 'error' && f.file.size > 0);
		failedFiles.forEach(f => {
			updateFile(f.id, {
				status: 'pending',
				progress: 0,
				error: undefined,
				taskId: undefined
			});
		});
		processUploadQueue();
	}

	$: retryableErrors = files.filter(f => f.status === 'error' && f.file.size > 0);
	$: hasRetryableErrors = retryableErrors.length > 0;

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
	}
</script>

<div 
	class="relative min-h-screen w-full overflow-hidden text-left pb-12"
	on:dragenter={handleWindowDragEnter}
	on:dragleave={handleWindowDragLeave}
	on:dragover|preventDefault
	on:drop={handleWindowDrop}
	role="region"
	aria-label="File Upload Area"
>
	<!-- Full page drag overlay -->
	{#if isWindowDragOver}
		<div class="fixed inset-0 bg-blue-600 bg-opacity-90 backdrop-blur-sm z-50 flex flex-col items-center justify-center text-white pointer-events-none transition-all duration-300">
			<div class="border-4 border-dashed border-white border-opacity-60 rounded-2xl p-12 flex flex-col items-center max-w-md pointer-events-none">
				<svg class="w-20 h-20 mb-4 animate-bounce pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
				</svg>
				<h2 class="text-2xl font-bold mb-2 pointer-events-none">Drop your photos & videos</h2>
				<p class="text-white text-opacity-80 text-center pointer-events-none">Release to upload files to this event</p>
			</div>
		</div>
	{/if}

	<!-- Ambient Background Orbs -->
	<div class="absolute top-0 left-0 w-full h-full pointer-events-none overflow-hidden z-0">
		<div class="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-indigo-500 opacity-[0.05] blur-[120px]"></div>
		<div class="absolute top-1/3 right-10 w-96 h-96 rounded-full bg-cyan-500 opacity-[0.04] blur-[120px]"></div>
		<div class="absolute bottom-10 left-1/3 w-96 h-96 rounded-full bg-purple-500 opacity-[0.03] blur-[120px]"></div>
	</div>

	<div class="relative z-10 max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
		{#if loading}
			<div class="text-center py-12">
				<div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent"></div>
				<p class="mt-2 text-gray-600 font-medium">Preparing upload area...</p>
			</div>
		{:else if error}
			<div class="bg-white rounded-xl shadow p-12 text-center border border-gray-100">
				<svg class="w-16 h-16 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
				</svg>
				<h2 class="text-xl font-bold text-gray-900 mb-2">
					{error.includes('paused') ? 'Upload Link Paused' : 'Upload Link Invalid'}
				</h2>
				<p class="text-gray-600">{error}</p>
			</div>
		{:else if folderInfo}
			<div class="text-center mb-8">
				<h1 class="text-3xl font-extrabold text-gray-900 tracking-tight mb-2">
					<span class="gps-title-gradient">{folderInfo.name}</span>
				</h1>
				<p class="text-gray-600">Upload photos and videos for <strong class="text-gray-800">{folderInfo.event_name}</strong></p>
			{#if folderInfo.readme_message}
				<div class="mt-6 mb-6 p-4 bg-gray-50 rounded-lg text-sm text-gray-700 max-w-xl mx-auto border border-gray-100 whitespace-pre-line text-left">
					{folderInfo.readme_message}
				</div>
			{/if}
		</div>

		<!-- Hidden input for Firefox upload compat -->
		<input
			bind:this={fileInput}
			id="file-upload-input"
			type="file"
			multiple
			accept={acceptString}
			class="sr-only"
			on:change={handleFileSelect}
		/>

		<!-- Drop Zone -->
		<label
			for="file-upload-input"
			class={`block border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer bg-white ${
				isDragOver
					? 'border-blue-500 bg-blue-50'
					: 'border-gray-300 hover:border-gray-400'
			}`}
			on:dragover={handleDragOver}
			on:dragleave={handleDragLeave}
			on:drop={handleDrop}
		>

			<svg class="w-12 h-12 text-gray-400 mx-auto mb-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
			</svg>

			<p class="text-lg text-gray-700 mb-2 pointer-events-none font-semibold">
				Drag & drop files here or <span class="text-blue-600 font-medium">browse your files</span>
			</p>
			<p class="text-sm text-gray-500 pointer-events-none">
				Supports: {allFormats.map(f => f.toUpperCase()).join(', ')}
			</p>
			<p class="text-xs text-gray-400 mt-2 pointer-events-none">Maximum size: {folderInfo.max_upload_size_mb}MB per file</p>
		</label>

		<!-- File List -->
		{#if files.length > 0}
			<div class="mt-6 space-y-2">
				<div class="flex justify-between items-center mb-3">
					<div class="flex items-center gap-3">
						<h2 class="text-lg font-bold text-gray-900">{files.length} file(s)</h2>
						{#if hasCompletedFiles}
							<div class="flex gap-1 text-xs">
								<span class="px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-semibold">{successCount} ✓</span>
								{#if errorCount > 0}
									<span class="px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-semibold">{errorCount} ✗</span>
								{/if}
							</div>
						{/if}
					</div>
					<div class="flex gap-2 items-center">
						<input 
							type="text" 
							placeholder="Filter list..." 
							bind:value={searchQuery}
							class="text-sm px-3 py-1 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-32"
						/>
						<button
							class="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 bg-transparent border-none cursor-pointer"
							on:click={() => showCompletedFiles = !showCompletedFiles}
						>
							{showCompletedFiles ? 'Hide Finished' : 'Show Finished'}
						</button>
					</div>
				</div>

				<!-- Active files (uploading/processing) -->
				{#each filteredActiveFiles as file (file.id)}
					<div class="bg-white rounded-lg shadow border border-gray-100 p-3 flex items-center gap-4">
						<div class="flex-shrink-0">
							<div class="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
						</div>
						<div class="flex-1 min-w-0">
							<p class="text-sm font-semibold truncate text-gray-800" title={file.file.name}>{file.file.name}</p>
							<div class="flex items-center gap-2 text-xs text-gray-500 mt-0.5">
								<span>{formatBytes(file.file.size)}</span>
								<span>•</span>
								<span>{file.status === 'uploading' ? 'Uploading...' : 'Converting/Saving...'}</span>
							</div>
						</div>
						<div class="w-20 bg-gray-100 rounded-full h-2">
							<div
								class="h-2 rounded-full bg-blue-600 transition-all duration-300"
								style="width: {file.progress}%"
							></div>
						</div>
					</div>
				{/each}

				<!-- Completed files -->
				{#if showCompletedFiles && filteredCompletedFiles.length > 0}
					<div class="space-y-1.5 pt-3 border-t border-gray-100">
						<div class="flex items-center justify-between">
							<span class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Finished Uploads</span>
							<div class="flex gap-2">
								{#if hasRetryableErrors}
									<button 
										class="text-xs text-orange-600 hover:text-orange-700 font-semibold bg-transparent border-none cursor-pointer p-0"
										on:click={retryAllFailed}
									>
										Retry All Failed ({retryableErrors.length})
									</button>
								{/if}
								<button 
									class="text-xs text-gray-400 hover:text-gray-600 bg-transparent border-none cursor-pointer p-0"
									on:click={clearCompletedFiles}
								>
									Clear Completed
								</button>
							</div>
						</div>
						{#each filteredCompletedFiles as file (file.id)}
							<div class="bg-white rounded-lg border border-gray-100 p-3 flex items-center gap-4 opacity-80 hover:opacity-100 transition-opacity">
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
									<p class="text-sm font-semibold truncate text-gray-800" title={file.file.name}>{file.file.name}</p>
									<div class="text-xs text-gray-500 mt-0.5">
										{formatBytes(file.file.size)}
										{#if file.error}
											<span class="text-red-500 ml-2 font-medium">{file.error}</span>
										{/if}
									</div>
								</div>
								{#if file.status === 'error' && file.file.size > 0}
									<button 
										class="text-xs text-orange-600 hover:bg-orange-50 px-2 py-1 rounded border border-orange-300 cursor-pointer"
										on:click={() => retryFile(file.id)}
									>
										Retry
									</button>
								{/if}
								<button class="text-gray-400 hover:text-gray-600 bg-transparent border-none cursor-pointer p-1" on:click={() => removeFileById(file.id)}>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
									</svg>
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Success Message / Shared Album view link -->
			{#if uploadComplete && successCount > 0 && folderInfo.nextcloud_share_url}
				<div class="mt-8 bg-green-50 border border-green-200 rounded-xl p-6 text-center">
					<svg class="w-12 h-12 text-green-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					<h3 class="text-xl font-bold text-green-800 mb-2">
						Upload Session Successful!
					</h3>
					<p class="text-green-700 mb-4 max-w-md mx-auto text-sm">
						Your photos and videos are successfully uploaded. Click the link below to view or download the shared album.
					</p>
					<a
						href={folderInfo.nextcloud_share_url}
						target="_blank"
						rel="noopener"
						class="inline-block px-5 py-2.5 bg-green-600 hover:bg-green-700 text-white font-bold rounded-lg shadow-sm no-underline"
					>
						View Shared Album
					</a>
				</div>
			{/if}
		{/if}

		<!-- Info footer -->
		<div class="mt-8 bg-gray-50 rounded-lg p-5 text-sm text-gray-600 border border-gray-100">
			<p class="font-bold text-gray-700 mb-2">How it works:</p>
			<ol class="list-decimal list-inside space-y-1">
				<li>Select or drag-and-drop your photos/videos.</li>
				<li>Files are securely transmitted and processed directly within our Nextcloud storage.</li>
				<li>Images are saved as JPEG (quality optimized), and videos are converted to highly compatible MP4 format.</li>
				<li>Original EXIF capture dates are extracted and used to automatically sort and name the files.</li>
			</ol>
		</div>
	{/if}
	</div>
</div>

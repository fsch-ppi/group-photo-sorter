<script lang="ts">
	import { page } from '$app/stores';
	import { upload, type FolderInfo, type TaskStatus } from '$lib/api';
	import { onMount } from 'svelte';
	import { fly, slide } from 'svelte/transition';
	import { flip } from 'svelte/animate';

	interface FileUpload {
		file: File;
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
	let shareToken = '';

	let files: FileUpload[] = [];
	let isDragOver = false;
	let fileInput: HTMLInputElement;
	let showCompletedFiles = true;
	let sessionId: string | null = null;
	let filterStatus: 'all' | 'active' | 'success' | 'error' = 'all';
	let searchQuery = '';

	$: shareToken = $page.params.token;
	$: allFormats = folderInfo
		? [...folderInfo.supported_image_formats, ...folderInfo.supported_video_formats]
		: [];
	$: acceptString = allFormats.map((f) => f).join(',');

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
	function getSessionId(): string | null {
		const cookies = document.cookie.split(';');
		for (const cookie of cookies) {
			const [name, value] = cookie.trim().split('=');
			if (name === `${SESSION_COOKIE_NAME}_${shareToken}`) {
				return value;
			}
		}
		return null;
	}

	function setSessionId(id: string) {
		const expires = new Date();
		expires.setDate(expires.getDate() + SESSION_DURATION_DAYS);
		document.cookie = `${SESSION_COOKIE_NAME}_${shareToken}=${id}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
	}

	function generateSessionId(): string {
		return crypto.randomUUID();
	}

	// Persist file state to localStorage
	function saveSessionState() {
		if (!sessionId) return;
		const state = files.map(f => ({
			name: f.file.name,
			size: f.file.size,
			status: f.status,
			taskId: f.taskId,
			error: f.error,
			result: f.result
		}));
		localStorage.setItem(`upload_session_${shareToken}_${sessionId}`, JSON.stringify(state));
	}

	function loadSessionState(): { name: string; size: number; status: string; taskId?: string; error?: string; result?: any }[] | null {
		if (!sessionId) return null;
		const stored = localStorage.getItem(`upload_session_${shareToken}_${sessionId}`);
		if (!stored) return null;
		try {
			return JSON.parse(stored);
		} catch {
			return null;
		}
	}

	onMount(async () => {
		// Get or create session
		sessionId = getSessionId();
		if (!sessionId) {
			sessionId = generateSessionId();
			setSessionId(sessionId);
		}

		await loadFolderInfo();

		// Restore session if exists
		const savedState = loadSessionState();
		if (savedState && savedState.length > 0) {
			// Restore completed/processing files from session
			for (const item of savedState) {
				if (item.status === 'success' || item.status === 'error') {
					// Create a placeholder file object for completed uploads
					const placeholderFile = new File([], item.name, { type: 'application/octet-stream' });
					Object.defineProperty(placeholderFile, 'size', { value: item.size });
					
					files = [...files, {
						file: placeholderFile,
						status: item.status as FileUpload['status'],
						progress: item.status === 'success' ? 100 : 0,
						taskId: item.taskId,
						error: item.error,
						result: item.result
					}];
				} else if (item.taskId && (item.status === 'processing' || item.status === 'uploading')) {
					// Check task status for in-progress uploads
					const placeholderFile = new File([], item.name, { type: 'application/octet-stream' });
					Object.defineProperty(placeholderFile, 'size', { value: item.size });
					
					const fileUpload: FileUpload = {
						file: placeholderFile,
						status: 'processing',
						progress: 50,
						taskId: item.taskId
					};
					files = [...files, fileUpload];
					
					// Resume polling for this task
					pollTaskStatus(files.length - 1, item.taskId);
				}
			}
			
			// Auto-hide completed files if there are any active ones
			if (activeFiles.length > 0 && completedFiles.length > 0) {
				showCompletedFiles = false;
			}
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
		if (input.files) {
			addFiles(Array.from(input.files));
		}
	}

	function addFiles(newFiles: File[]) {
		// Check if folder info is loaded
		if (!folderInfo || allFormats.length === 0) {
			alert('Please wait for the page to finish loading before uploading files.');
			return;
		}

		const validFiles = newFiles.filter((file) => {
			const ext = '.' + file.name.split('.').pop()?.toLowerCase();
			const isValid = allFormats.includes(ext);
			if (!isValid) {
				console.log(`Rejected file ${file.name}: extension ${ext} not in ${allFormats.join(', ')}`);
			}
			return isValid;
		});

		if (validFiles.length === 0 && newFiles.length > 0) {
			const exts = newFiles.map(f => '.' + f.name.split('.').pop()?.toLowerCase()).join(', ');
			alert(`No valid files found. Supported formats: ${allFormats.join(', ')}\nYour files: ${exts}`);
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
			file,
			status: 'pending',
			progress: 0
		}));

		files = [...files, ...newUploads];

		// Start uploading
		okFiles.forEach((_, index) => {
			uploadFile(files.length - okFiles.length + index);
		});
	}

	async function uploadFile(index: number) {
		const fileUpload = files[index];
		files[index] = { ...fileUpload, status: 'uploading', progress: 10 };
		files = files;
		saveSessionState();

		try {
			const result = await upload.uploadFile(shareToken, fileUpload.file);
			files[index] = {
				...files[index],
				status: 'processing',
				progress: 50,
				taskId: result.task_id
			};
			files = files;
			saveSessionState();

			// Poll for task completion
			pollTaskStatus(index, result.task_id);
		} catch (e) {
			files[index] = {
				...files[index],
				status: 'error',
				error: e instanceof Error ? e.message : 'Upload failed'
			};
			files = files;
			saveSessionState();
		}
	}

	async function pollTaskStatus(index: number, taskId: string) {
		let attempts = 0;
		const maxAttempts = 360; // 30 minutes max for large videos

		while (attempts < maxAttempts) {
			try {
				const status = await upload.taskStatus(taskId);

				if (status.status === 'SUCCESS' && status.result) {
					files[index] = {
						...files[index],
						status: 'success',
						progress: 100,
						result: status.result
					};
					files = files;
					saveSessionState();
					
					// Auto-hide completed files after a short delay when new files complete
					if (activeFiles.length > 0) {
						setTimeout(() => {
							showCompletedFiles = false;
						}, 2000);
					}
					return;
				} else if (status.status === 'FAILURE') {
					files[index] = {
						...files[index],
						status: 'error',
						error: status.error || 'Processing failed'
					};
					files = files;
					saveSessionState();
					return;
				}

				// Update progress estimate
				const progressEstimate = Math.min(50 + attempts, 95);
				files[index] = { ...files[index], progress: progressEstimate };
				files = files;
			} catch (e) {
				console.error('Failed to check task status:', e);
			}

			attempts++;
			await new Promise((resolve) => setTimeout(resolve, 5000));
		}

		files[index] = {
			...files[index],
			status: 'error',
			error: 'Processing timed out'
		};
		files = files;
		saveSessionState();
	}

	function removeFile(index: number) {
		files = files.filter((_, i) => i !== index);
		saveSessionState();
	}

	function clearCompletedFiles() {
		files = files.filter((f) => f.status !== 'success' && f.status !== 'error');
		saveSessionState();
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
	}

	function getStatusColor(status: FileUpload['status']): string {
		switch (status) {
			case 'success':
				return 'bg-green-500';
			case 'error':
				return 'bg-red-500';
			case 'uploading':
			case 'processing':
				return 'bg-primary-500';
			default:
				return 'bg-gray-300';
		}
	}

	function getStatusText(upload: FileUpload): string {
		switch (upload.status) {
			case 'pending':
				return 'Waiting...';
			case 'uploading':
				return 'Uploading...';
			case 'processing':
				return 'Converting...';
			case 'success':
				return `Done → ${upload.result?.filename}`;
			case 'error':
				return upload.error || 'Failed';
		}
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
		</div>

		<!-- Drop Zone -->
		<div
			class={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
				isDragOver
					? 'border-primary-500 bg-primary-50'
					: 'border-gray-300 hover:border-gray-400'
			}`}
			on:dragover={handleDragOver}
			on:dragleave={handleDragLeave}
			on:drop={handleDrop}
			role="button"
			tabindex="0"
			on:keypress={(e) => e.key === 'Enter' && fileInput.click()}
			on:click={() => fileInput.click()}
		>
			<input
				bind:this={fileInput}
				type="file"
				multiple
				accept={acceptString}
				class="hidden"
				on:change={handleFileSelect}
			/>

			<svg class="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
			</svg>

			<p class="text-lg text-gray-700 mb-2">
				Drag & drop files here or <span class="text-primary-600 font-medium">browse</span>
			</p>
			<p class="text-sm text-gray-500">
				Supports images ({folderInfo.supported_image_formats.join(', ')}) and videos ({folderInfo.supported_video_formats.join(', ')})
			</p>
			<p class="text-xs text-gray-400 mt-2">Max file size: {folderInfo.max_upload_size_mb}MB</p>
		</div>

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
						<!-- Search -->
						<input 
							type="text" 
							placeholder="Search files..." 
							bind:value={searchQuery}
							class="text-sm px-2 py-1 border rounded-md w-32 focus:outline-none focus:ring-1 focus:ring-primary-500"
						/>
						<!-- Filter buttons -->
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

				<!-- Active files (uploading/processing) - always visible, compact -->
				{#each filteredActiveFiles as file, index (file.taskId || file.file.name + index)}
					<div 
						class="bg-white rounded-lg shadow-sm p-2 flex items-center gap-3"
						animate:flip={{ duration: 300 }}
						transition:slide={{ duration: 300 }}
					>
						<!-- Status icon -->
						<div class="flex-shrink-0">
							{#if file.status === 'uploading' || file.status === 'processing'}
								<div class="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
							{:else}
								<div class="w-5 h-5 rounded-full bg-gray-200"></div>
							{/if}
						</div>
						<!-- File info -->
						<div class="flex-1 min-w-0">
							<p class="text-sm font-medium truncate" title={file.file.name}>{file.file.name}</p>
							<div class="flex items-center gap-2 text-xs text-gray-500">
								<span>{formatBytes(file.file.size)}</span>
								<span>•</span>
								<span>{file.status === 'uploading' ? 'Uploading...' : 'Converting...'}</span>
							</div>
						</div>
						<!-- Progress bar (mini) -->
						<div class="w-16 bg-gray-200 rounded-full h-1.5">
							<div
								class="h-1.5 rounded-full bg-primary-500 transition-all duration-300"
								style="width: {file.progress}%"
							></div>
						</div>
						{#if file.status === 'pending'}
							<button class="text-gray-400 hover:text-gray-600 p-1" on:click={() => removeFile(files.indexOf(file))}>
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</button>
						{/if}
					</div>
				{/each}

				<!-- Completed files - collapsible, compact -->
				{#if showCompletedFiles && filteredCompletedFiles.length > 0}
					<div transition:slide={{ duration: 300 }} class="space-y-1 pt-2 border-t">
						<div class="flex items-center justify-between">
							<span class="text-xs text-gray-400">Completed</span>
							<button 
								class="text-xs text-gray-400 hover:text-gray-600"
								on:click={clearCompletedFiles}
							>
								Clear
							</button>
						</div>
						{#each filteredCompletedFiles as file, index (file.taskId || file.file.name + 'completed' + index)}
							<div 
								class="bg-white rounded-lg shadow-sm p-2 flex items-center gap-3 opacity-75 hover:opacity-100 transition-opacity"
								animate:flip={{ duration: 300 }}
								in:fly={{ y: -10, duration: 200 }}
								out:fly={{ x: 50, duration: 150 }}
							>
								<!-- Status icon -->
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
								<!-- File info -->
								<div class="flex-1 min-w-0">
									<p class="text-sm truncate" title={file.file.name}>{file.file.name}</p>
									<div class="text-xs text-gray-500">
										{formatBytes(file.file.size)}
										{#if file.result}
											→ {formatBytes(file.result.converted_size)}
										{/if}
										{#if file.error}
											<span class="text-red-500 ml-1">{file.error}</span>
										{/if}
									</div>
								</div>
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
						Your photos are now being processed and will appear in the shared folder.
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
				<li>Files are organized and named by date</li>
				<li>Click the link above to view and download all photos</li>
			</ol>
		</div>
	{/if}
</div>

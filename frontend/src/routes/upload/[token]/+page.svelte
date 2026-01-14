<script lang="ts">
	import { page } from '$app/stores';
	import { upload, type FolderInfo, type TaskStatus } from '$lib/api';
	import { onMount } from 'svelte';

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

	let folderInfo: FolderInfo | null = null;
	let loading = true;
	let error = '';
	let shareToken = '';

	let files: FileUpload[] = [];
	let isDragOver = false;
	let fileInput: HTMLInputElement;

	$: shareToken = $page.params.token;
	$: allFormats = folderInfo
		? [...folderInfo.supported_image_formats, ...folderInfo.supported_video_formats]
		: [];
	$: acceptString = allFormats.map((f) => f).join(',');

	$: uploadComplete =
		files.length > 0 &&
		files.every((f) => f.status === 'success' || f.status === 'error');
	$: successCount = files.filter((f) => f.status === 'success').length;

	onMount(async () => {
		await loadFolderInfo();
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
		const validFiles = newFiles.filter((file) => {
			const ext = '.' + file.name.split('.').pop()?.toLowerCase();
			return allFormats.includes(ext);
		});

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

		try {
			const result = await upload.uploadFile(shareToken, fileUpload.file);
			files[index] = {
				...files[index],
				status: 'processing',
				progress: 50,
				taskId: result.task_id
			};
			files = files;

			// Poll for task completion
			pollTaskStatus(index, result.task_id);
		} catch (e) {
			files[index] = {
				...files[index],
				status: 'error',
				error: e instanceof Error ? e.message : 'Upload failed'
			};
			files = files;
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
					return;
				} else if (status.status === 'FAILURE') {
					files[index] = {
						...files[index],
						status: 'error',
						error: status.error || 'Processing failed'
					};
					files = files;
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
	}

	function removeFile(index: number) {
		files = files.filter((_, i) => i !== index);
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
			<div class="mt-8 space-y-3">
				<div class="flex justify-between items-center">
					<h2 class="text-lg font-semibold">{files.length} file(s)</h2>
					{#if uploadComplete && successCount > 0 && folderInfo.nextcloud_share_url}
						<a href={folderInfo.nextcloud_share_url} target="_blank" rel="noopener" class="btn btn-primary">
							View All Photos →
						</a>
					{/if}
				</div>

				{#each files as file, index}
					<div class="bg-white rounded-lg shadow p-4">
						<div class="flex justify-between items-start mb-2">
							<div class="flex-1 min-w-0">
								<p class="font-medium truncate">{file.file.name}</p>
								<p class="text-sm text-gray-500">
									{formatBytes(file.file.size)}
									{#if file.result}
										→ {formatBytes(file.result.converted_size)}
									{/if}
								</p>
							</div>
							{#if file.status === 'pending'}
								<button class="text-gray-400 hover:text-gray-600 ml-2" on:click={() => removeFile(index)}>
									<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
									</svg>
								</button>
							{/if}
						</div>

						<!-- Progress bar -->
						<div class="w-full bg-gray-200 rounded-full h-2 mb-2">
							<div
								class={`h-2 rounded-full transition-all duration-300 ${getStatusColor(file.status)}`}
								style="width: {file.progress}%"
							></div>
						</div>

						<p class={`text-sm ${file.status === 'error' ? 'text-red-600' : file.status === 'success' ? 'text-green-600' : 'text-gray-600'}`}>
							{getStatusText(file)}
						</p>
					</div>
				{/each}
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

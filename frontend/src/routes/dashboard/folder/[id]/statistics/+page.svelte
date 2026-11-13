<script lang="ts">
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import { folders, type FolderStatistics, type PhotoFolder } from '$lib/api';
	import { onMount } from 'svelte';

	let folder: PhotoFolder | null = null;
	let stats: FolderStatistics | null = null;
	let loading = true;
	let error = '';

	$: folderId = parseInt($page.params.id || '0', 10);

	onMount(async () => {
		await loadData();
	});

	async function loadData() {
		loading = true;
		error = '';
		try {
			[folder, stats] = await Promise.all([
				folders.get(folderId),
				folders.statistics(folderId)
			]);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load data';
		} finally {
			loading = false;
		}
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
	}

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleString();
	}
</script>

<svelte:head>
	<title>{folder?.name || 'Statistics'} - Photo Import Sorter</title>
</svelte:head>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
	<a href="{base}/dashboard" class="text-primary-600 hover:text-primary-700 mb-4 inline-block">
		← Back to Dashboard
	</a>

	{#if loading}
		<div class="text-center py-12">
			<div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
			<p class="mt-2 text-gray-600">Loading statistics...</p>
		</div>
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
			{error}
		</div>
	{:else if folder && stats}
		<h1 class="text-3xl font-bold text-gray-900 mb-8">{folder.name} - Statistics</h1>

		<!-- Summary Cards -->
		<div class="grid md:grid-cols-4 gap-6 mb-8">
			<div class="card">
				<p class="text-sm text-gray-500 mb-1">Total Uploads</p>
				<p class="text-3xl font-bold text-gray-900">{stats.total_uploads}</p>
			</div>
			<div class="card">
				<p class="text-sm text-gray-500 mb-1">Original Size</p>
				<p class="text-3xl font-bold text-gray-900">{formatBytes(stats.total_size_original_bytes)}</p>
			</div>
			<div class="card">
				<p class="text-sm text-gray-500 mb-1">Converted Size</p>
				<p class="text-3xl font-bold text-gray-900">{formatBytes(stats.total_size_converted_bytes)}</p>
			</div>
			<div class="card">
				<p class="text-sm text-gray-500 mb-1">Space Saved</p>
				<p class="text-3xl font-bold text-green-600">
					{#if stats.total_size_original_bytes > 0}
						{Math.round((1 - stats.total_size_converted_bytes / stats.total_size_original_bytes) * 100)}%
					{:else}
						0%
					{/if}
				</p>
			</div>
		</div>

		<!-- Uploads by IP -->
		{#if Object.keys(stats.uploads_by_ip).length > 0}
			<div class="card mb-8">
				<h2 class="text-xl font-semibold mb-4">Uploads by IP Address</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-left">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-3 font-medium text-gray-600">IP Address</th>
								<th class="px-4 py-3 font-medium text-gray-600">Upload Count</th>
							</tr>
						</thead>
						<tbody class="divide-y">
							{#each Object.entries(stats.uploads_by_ip).sort((a, b) => b[1] - a[1]) as [ip, count]}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-3 font-mono text-sm">{ip}</td>
									<td class="px-4 py-3">{count}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		<!-- Recent Uploads -->
		{#if stats.recent_uploads.length > 0}
			<div class="card">
				<h2 class="text-xl font-semibold mb-4">Recent Uploads</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-left">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-3 font-medium text-gray-600">Original Name</th>
								<th class="px-4 py-3 font-medium text-gray-600">Converted Name</th>
								<th class="px-4 py-3 font-medium text-gray-600">Type</th>
								<th class="px-4 py-3 font-medium text-gray-600">Size</th>
								<th class="px-4 py-3 font-medium text-gray-600">Time</th>
								<th class="px-4 py-3 font-medium text-gray-600">Date</th>
							</tr>
						</thead>
						<tbody class="divide-y">
							{#each stats.recent_uploads as upload}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-3 text-sm truncate max-w-xs" title={upload.filename_original}>{upload.filename_original}</td>
									<td class="px-4 py-3 text-sm truncate max-w-xs" title={upload.filename_converted}>{upload.filename_converted}</td>
									<td class="px-4 py-3">
										<span class={`px-2 py-1 rounded-full text-xs font-medium ${upload.file_type === 'video' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'}`}>
											{upload.file_type}
										</span>
									</td>
									<td class="px-4 py-3 text-sm">
										{formatBytes(upload.file_size_original)} → {formatBytes(upload.file_size_converted)}
									</td>
									<td class="px-4 py-3 text-sm">{upload.conversion_time_seconds.toFixed(1)}s</td>
									<td class="px-4 py-3 text-sm">{formatDate(upload.uploaded_at)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{:else}
			<div class="card text-center py-8">
				<p class="text-gray-500">No uploads yet</p>
			</div>
		{/if}
	{/if}
</div>

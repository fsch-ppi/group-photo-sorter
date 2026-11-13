<script lang="ts">
	import { base } from '$app/paths';
	import { auth, type User } from '$lib/api';
	import { onMount } from 'svelte';

	let user: User | null = null;
	let loading = true;

	onMount(async () => {
		try {
			const status = await auth.status();
			if (status.authenticated && status.user) {
				user = status.user;
			}
		} catch (e) {
			console.error('Auth check failed:', e);
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Photo Import Sorter - Home</title>
</svelte:head>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
	<!-- Hero Section -->
	<div class="text-center mb-16">
		<h1 class="text-4xl sm:text-5xl font-bold text-gray-900 mb-4">
			Collect & Convert Photos
			<span class="text-primary-600">Effortlessly</span>
		</h1>
		<p class="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
			Create shareable upload links, automatically convert photos and videos to standard formats,
			and store everything organized in your Nextcloud.
		</p>

		{#if !loading}
			{#if user}
				<a href="{base}/dashboard" class="btn btn-primary text-lg px-8 py-3"> Go to Dashboard </a>
			{:else}
				<a href="{base}/api/auth/login/" data-sveltekit-reload rel="external" class="btn btn-primary text-lg px-8 py-3">
					Login with Nextcloud
				</a>
			{/if}
		{/if}
	</div>

	<!-- Features -->
	<div class="grid md:grid-cols-3 gap-8 mb-16">
		<div class="card text-center">
			<div class="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
				<svg class="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
					/>
				</svg>
			</div>
			<h3 class="text-xl font-semibold mb-2">Easy Uploads</h3>
			<p class="text-gray-600">
				Share a simple link. Anyone can upload photos and videos without needing an account.
			</p>
		</div>

		<div class="card text-center">
			<div class="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
				<svg class="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
					/>
				</svg>
			</div>
			<h3 class="text-xl font-semibold mb-2">Auto-Convert</h3>
			<p class="text-gray-600">
				HEIC, RAW, MOV? No problem. All files are converted to JPEG and MP4 automatically.
			</p>
		</div>

		<div class="card text-center">
			<div class="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
				<svg class="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
					/>
				</svg>
			</div>
			<h3 class="text-xl font-semibold mb-2">Organized Storage</h3>
			<p class="text-gray-600">
				Files are named by date and event, stored directly in your Nextcloud with a shareable
				download link.
			</p>
		</div>
	</div>

	<!-- How it works -->
	<div class="bg-white rounded-2xl shadow-lg p-8 mb-16">
		<h2 class="text-2xl font-bold text-center mb-8">How It Works</h2>
		<div class="grid md:grid-cols-4 gap-6">
			<div class="text-center">
				<div
					class="w-10 h-10 bg-primary-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 font-bold"
				>
					1
				</div>
				<h4 class="font-semibold mb-1">Create Folder</h4>
				<p class="text-sm text-gray-600">Set up a folder for your event with your preferences</p>
			</div>
			<div class="text-center">
				<div
					class="w-10 h-10 bg-primary-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 font-bold"
				>
					2
				</div>
				<h4 class="font-semibold mb-1">Share Link</h4>
				<p class="text-sm text-gray-600">Get a unique upload link to share with guests</p>
			</div>
			<div class="text-center">
				<div
					class="w-10 h-10 bg-primary-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 font-bold"
				>
					3
				</div>
				<h4 class="font-semibold mb-1">Collect Photos</h4>
				<p class="text-sm text-gray-600">Guests upload directly from their devices</p>
			</div>
			<div class="text-center">
				<div
					class="w-10 h-10 bg-primary-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 font-bold"
				>
					4
				</div>
				<h4 class="font-semibold mb-1">Download</h4>
				<p class="text-sm text-gray-600">All converted files ready in your Nextcloud</p>
			</div>
		</div>
	</div>
</div>

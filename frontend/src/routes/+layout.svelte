<script lang="ts">
	import { auth, type User } from '$lib/api';
	import { onMount } from 'svelte';
	import '../app.css';

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

	async function handleLogout() {
		try {
			await auth.logout();
			user = null;
			window.location.href = '/';
		} catch (e) {
			console.error('Logout failed:', e);
		}
	}
</script>

<div class="min-h-screen bg-gray-50">
	<!-- Header -->
	<header class="bg-white shadow-sm">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
			<div class="flex justify-between items-center h-16">
				<a href="/" class="flex items-center space-x-2">
					<svg
						class="w-8 h-8 text-primary-600"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
						/>
					</svg>
					<span class="text-xl font-bold text-gray-900">Photo Import Sorter</span>
				</a>

				{#if !loading}
					<nav class="flex items-center space-x-4">
						{#if user}
							<a href="/dashboard" class="text-gray-600 hover:text-gray-900">Dashboard</a>
							<span class="text-gray-400">|</span>
							<span class="text-gray-600">{user.username}</span>
							<button on:click={handleLogout} class="btn btn-secondary text-sm"> Logout </button>
						{:else}
							<a href="/api/auth/login/" class="btn btn-primary"> Login with Nextcloud </a>
						{/if}
					</nav>
				{/if}
			</div>
		</div>
	</header>

	<!-- Main content -->
	<main>
		<slot />
	</main>

	<!-- Footer -->
	<footer class="bg-white border-t mt-auto">
		<div class="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
			<p class="text-center text-gray-500 text-sm">
				Photo Import Sorter &copy; {new Date().getFullYear()}
			</p>
		</div>
	</footer>
</div>

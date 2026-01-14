<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';

	export let onConsent: ((type: 'essential' | 'rejected') => void) | undefined = undefined;

	let showBanner = false;
	let showDetails = false;

	onMount(() => {
		// Check if consent was already given
		const consent = getCookieConsent();
		if (!consent) {
			showBanner = true;
		}
	});

	function getCookieConsent(): string | null {
		const cookies = document.cookie.split(';');
		for (const cookie of cookies) {
			const [name, value] = cookie.trim().split('=');
			if (name === 'cookie_consent') {
				return value;
			}
		}
		return null;
	}

	async function acceptEssential() {
		await setConsent('essential');
		showBanner = false;
		onConsent?.('essential');
	}

	async function rejectAll() {
		await setConsent('rejected');
		showBanner = false;
		onConsent?.('rejected');
	}

	async function setConsent(type: 'essential' | 'rejected') {
		try {
			await fetch('/api/auth/cookie-consent/', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({ consent: type }),
				credentials: 'include',
			});
		} catch (e) {
			// Fallback: set cookie directly
			const expires = new Date();
			expires.setFullYear(expires.getFullYear() + 1);
			document.cookie = `cookie_consent=${type}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
		}
	}
</script>

{#if showBanner}
	<div
		class="fixed bottom-0 left-0 right-0 z-50 bg-white border-t shadow-lg"
		transition:slide={{ duration: 300 }}
	>
		<div class="max-w-4xl mx-auto p-4 sm:p-6">
			<div class="flex flex-col sm:flex-row items-start sm:items-center gap-4">
				<div class="flex-1">
					<h3 class="font-semibold text-gray-900 mb-1">🍪 Cookie & Privacy Notice</h3>
					<p class="text-sm text-gray-600">
						We use only <strong>essential cookies</strong> required for the application to function. 
						No tracking or advertising cookies are used.
					</p>
					
					{#if showDetails}
						<div class="mt-3 p-3 bg-gray-50 rounded-lg text-sm" transition:slide>
							<p class="font-medium text-gray-700 mb-2">What we use:</p>
							<ul class="space-y-1 text-gray-600">
								<li>• <strong>Session Cookie</strong> – Maintains your login (7 days)</li>
								<li>• <strong>CSRF Token</strong> – Security protection (session)</li>
								<li>• <strong>Consent Cookie</strong> – Remembers this choice (1 year)</li>
							</ul>
							<p class="mt-3 font-medium text-gray-700 mb-1">Data processing:</p>
							<ul class="space-y-1 text-gray-600">
								<li>• IP addresses are <strong>anonymized after 30 days</strong></li>
								<li>• Uploaded files are stored in <strong>your Nextcloud</strong></li>
								<li>• No data is shared with third parties</li>
							</ul>
							<a href="/api/auth/privacy/" target="_blank" class="inline-block mt-2 text-primary-600 hover:underline">
								Full Privacy Policy →
							</a>
						</div>
					{/if}
					
					<button
						class="text-sm text-primary-600 hover:underline mt-1"
						on:click={() => showDetails = !showDetails}
					>
						{showDetails ? 'Hide details' : 'Show details'}
					</button>
				</div>
				
				<div class="flex gap-2 flex-shrink-0">
					<button
						class="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
						on:click={rejectAll}
					>
						Reject All
					</button>
					<button
						class="px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
						on:click={acceptEssential}
					>
						Accept Essential
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}

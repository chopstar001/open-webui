<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';

	import { WEBUI_NAME } from '$lib/stores';
	import { getUserInvoices, type PaymentInvoice } from '$lib/apis/billing';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';
	import { showSidebar } from '$lib/stores';

	const i18n = getContext('i18n');

	let loaded = false;
	let invoices: PaymentInvoice[] = [];

	const statusLabels: Record<string, string> = {
		pending: 'Pending',
		confirming: 'Confirming',
		confirmed: 'Confirmed',
		expired: 'Expired',
		failed: 'Failed'
	};

	const statusColors: Record<string, string> = {
		pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
		confirming: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
		confirmed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
		expired: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
		failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
	};

	const formatDate = (timestamp: number) => {
		return new Date(timestamp * 1000).toLocaleString();
	};

	const planNames: Record<string, string> = {
		free: 'Free',
		pro: 'Pro',
		ultra: 'Ultra'
	};

	onMount(async () => {
		try {
			invoices = await getUserInvoices(localStorage.token);
		} catch (err) {
			console.error('Failed to load invoices:', err);
			toast.error('Failed to load invoices');
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>{$i18n.t('Invoices')} | {$WEBUI_NAME}</title>
</svelte:head>

{#if loaded}
	<div class="flex flex-col w-full h-full overflow-y-auto">
		<!-- Header -->
		<div class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 dark:border-gray-900">
			<button
				class="md:hidden p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
				on:click={() => showSidebar.set(!$showSidebar)}
			>
				<SidebarIcon className="size-5" />
			</button>
			<button
				class="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
				on:click={() => goto('/billing')}
			>
				← {$i18n.t('Plans')}
			</button>
			<h1 class="text-lg font-semibold ml-2">{$i18n.t('Invoice History')}</h1>
		</div>

		<!-- Content -->
		<div class="flex-1 p-4 md:p-8">
			<div class="max-w-3xl mx-auto">
				{#if invoices.length === 0}
					<div class="text-center py-20">
						<p class="text-gray-500 dark:text-gray-400">{$i18n.t('No invoices yet')}</p>
						<button
							class="mt-4 px-6 py-2 rounded-xl text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 transition"
							on:click={() => goto('/billing')}
						>
							{$i18n.t('Browse plans')}
						</button>
					</div>
				{:else}
					<div class="space-y-3">
						{#each invoices as invoice}
							<div
								class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4"
							>
								<div class="flex items-center justify-between">
									<div class="flex items-center gap-3">
										<div>
											<div class="flex items-center gap-2">
												<span class="font-medium text-sm">
													{planNames[invoice.plan_id] || invoice.plan_id}
												</span>
												<span
													class="px-2 py-0.5 text-xs font-medium rounded-full {statusColors[
														invoice.status
													] || statusColors.pending}"
												>
													{statusLabels[invoice.status] || invoice.status}
												</span>
											</div>
											<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
												{formatDate(invoice.created_at)}
											</div>
										</div>
									</div>
									<div class="text-right">
										<div class="text-sm font-medium">
											${invoice.fiat_amount} {invoice.fiat_currency}
										</div>
										{#if invoice.crypto_amount}
											<div class="text-xs text-gray-500 dark:text-gray-400">
												{invoice.crypto_amount.toFixed(6)}
												{invoice.crypto_currency}
											</div>
										{/if}
									</div>
								</div>
								{#if invoice.tx_hash}
									<div class="mt-2 text-xs text-gray-400 dark:text-gray-600">
										TX: {invoice.tx_hash}
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	</div>
{:else}
	<div class="flex items-center justify-center h-full">
		<Spinner />
	</div>
{/if}

<script lang="ts">
	import { onMount, getContext, onDestroy } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { WEBUI_NAME, user } from '$lib/stores';
	import {
		createInvoice,
		getInvoice,
		cancelSubscription,
		type InvoiceCreateResponse,
		type PaymentInvoice
	} from '$lib/apis/billing';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';
	import { showSidebar } from '$lib/stores';

	const i18n = getContext('i18n');

	const TIMEOUT_SECONDS = 30 * 60; // 30 minutes

	let loading = true;
	let creating = true;
	let invoiceResponse: InvoiceCreateResponse | null = null;
	let invoiceStatus: PaymentInvoice | null = null;
	let pollTimer: ReturnType<typeof setInterval> | null = null;
	let countdownTimer: ReturnType<typeof setInterval> | null = null;
	let cancelled = false;

	let planId = '';
	let cryptoCurrency = 'XRP';

	// Countdown
	let secondsRemaining = TIMEOUT_SECONDS;
	$: minutes = Math.floor(secondsRemaining / 60);
	$: seconds = secondsRemaining % 60;
	$: countdownDisplay = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
	$: countdownProgress = (secondsRemaining / TIMEOUT_SECONDS) * 100;
	$: isUrgent = secondsRemaining < 300; // Last 5 minutes

	// Status display
	const statusLabels: Record<string, string> = {
		pending: 'Waiting for payment',
		confirming: 'Confirming payment',
		confirmed: 'Payment confirmed!',
		expired: 'Invoice expired',
		failed: 'Payment failed',
		cancelled: 'Cancelled'
	};

	const statusColors: Record<string, string> = {
		pending: 'text-yellow-600 dark:text-yellow-400',
		confirming: 'text-blue-600 dark:text-blue-400',
		confirmed: 'text-green-600 dark:text-green-400',
		expired: 'text-red-600 dark:text-red-400',
		failed: 'text-red-600 dark:text-red-400',
		cancelled: 'text-gray-600 dark:text-gray-400'
	};

	const createPaymentInvoice = async () => {
		creating = true;
		try {
			invoiceResponse = await createInvoice(localStorage.token, planId, cryptoCurrency);
			toast.success('Invoice created');
			startCountdown();
			startPolling();
		} catch (err: any) {
			console.error('Failed to create invoice:', err);
			toast.error(typeof err === 'string' ? err : 'Failed to create invoice');
		}
		creating = false;
	};

	const startCountdown = () => {
		secondsRemaining = TIMEOUT_SECONDS;
		countdownTimer = setInterval(() => {
			secondsRemaining -= 1;
			if (secondsRemaining <= 0) {
				stopCountdown();
				stopPolling();
				if (invoiceStatus?.status !== 'confirmed') {
					invoiceStatus = { ...invoiceStatus, status: 'expired' } as PaymentInvoice;
				}
			}
		}, 1000);
	};

	const stopCountdown = () => {
		if (countdownTimer) {
			clearInterval(countdownTimer);
			countdownTimer = null;
		}
	};

	const startPolling = () => {
		pollTimer = setInterval(async () => {
			if (!invoiceResponse) return;
			try {
				invoiceStatus = await getInvoice(localStorage.token, invoiceResponse.invoice_id);
				if (invoiceStatus?.status === 'confirmed') {
					toast.success('Payment confirmed! Your subscription is now active.');
					stopPolling();
					stopCountdown();
				} else if (invoiceStatus?.status === 'expired' || invoiceStatus?.status === 'failed') {
					stopPolling();
					stopCountdown();
				}
			} catch (err) {
				console.error('Poll error:', err);
			}
		}, 3000);
	};

	const stopPolling = () => {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	};

	const handleCancel = async () => {
		stopPolling();
		stopCountdown();
		cancelled = true;
		toast.success('Payment cancelled');
		// Small delay so user sees the cancelled state
		setTimeout(() => goto('/billing'), 1500);
	};

	const copyToClipboard = (text: string) => {
		navigator.clipboard.writeText(text);
		toast.success('Copied to clipboard');
	};

	onMount(() => {
		planId = $page.url.searchParams.get('plan') || '';
		if (!planId) {
			toast.error('No plan selected');
			goto('/billing');
			return;
		}
		createPaymentInvoice();
	});

	onDestroy(() => {
		stopPolling();
		stopCountdown();
	});
</script>

<svelte:head>
	<title>{$i18n.t('Checkout')} | {$WEBUI_NAME}</title>
</svelte:head>

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
			← {$i18n.t('Back to plans')}
		</button>
		<h1 class="text-lg font-semibold ml-2">{$i18n.t('Checkout')}</h1>
	</div>

	<!-- Content -->
	<div class="flex-1 p-4 md:p-8 flex items-start justify-center">
		<div class="w-full max-w-md">
			{#if creating}
				<div class="flex flex-col items-center justify-center py-20">
					<Spinner />
					<p class="mt-4 text-sm text-gray-500 dark:text-gray-400">
						{$i18n.t('Creating invoice...')}
					</p>
				</div>
			{:else if cancelled}
				<div class="flex flex-col items-center justify-center py-20">
					<div class="text-4xl mb-4">🚫</div>
					<h3 class="text-lg font-semibold text-gray-600 dark:text-gray-400">
						{$i18n.t('Payment Cancelled')}
					</h3>
					<p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
						{$i18n.t('Redirecting to plans...')}
					</p>
				</div>
			{:else if invoiceResponse}
				<div class="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
					<!-- Invoice Header -->
					<div class="p-6 border-b border-gray-100 dark:border-gray-800">
						<div class="flex items-center justify-between">
							<h2 class="text-lg font-semibold">Pay with {invoiceResponse.crypto}</h2>
							<span
								class="px-3 py-1 text-xs font-medium rounded-full {statusColors[
									invoiceStatus?.status || 'pending'
								]} bg-gray-100 dark:bg-gray-800"
							>
								{statusLabels[invoiceStatus?.status || 'pending'] || 'Pending'}
							</span>
						</div>
						<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
							${invoiceResponse.fiat_amount} USD
						</p>
					</div>

					<!-- Countdown Timer -->
					{#if invoiceStatus?.status !== 'confirmed' && invoiceStatus?.status !== 'expired' && invoiceStatus?.status !== 'cancelled'}
						<div class="px-6 pt-4">
							<div class="flex items-center justify-between mb-1">
								<span class="text-xs text-gray-500 dark:text-gray-400">
									{$i18n.t('Time remaining')}
								</span>
								<span class="text-xs font-mono {isUrgent ? 'text-red-500 font-bold' : 'text-gray-600 dark:text-gray-300'}">
									{countdownDisplay}
								</span>
							</div>
							<div class="w-full h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
								<div
									class="h-full rounded-full transition-all duration-1000 {isUrgent
										? 'bg-red-500'
										: countdownProgress > 50
											? 'bg-green-500'
											: 'bg-yellow-500'}"
									style="width: {countdownProgress}%"
								/>
							</div>
						</div>
					{/if}

					<!-- Payment Details -->
					{#if invoiceStatus?.status !== 'confirmed' && invoiceStatus?.status !== 'expired' && invoiceStatus?.status !== 'cancelled'}
						<div class="p-6 space-y-4">
							<!-- Amount -->
							<div>
								<label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
									{$i18n.t('Amount to send')}
								</label>
								<div class="flex items-center gap-2">
									<code
										class="flex-1 p-3 bg-gray-50 dark:bg-gray-850 rounded-lg text-lg font-mono font-bold select-all"
									>
										{invoiceResponse.amount} {invoiceResponse.crypto}
									</code>
									<button
										class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition text-gray-500"
										on:click={() => copyToClipboard(invoiceResponse.amount)}
										title="Copy amount"
									>
										📋
									</button>
								</div>
							</div>

							<!-- Address -->
							<div>
								<label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
									{$i18n.t('Send to address')}
								</label>
								<div class="flex items-center gap-2">
									<code
										class="flex-1 p-3 bg-gray-50 dark:bg-gray-850 rounded-lg text-xs font-mono break-all select-all"
									>
										{invoiceResponse.wallet}
									</code>
									<button
										class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition text-gray-500"
										on:click={() => copyToClipboard(invoiceResponse.wallet)}
										title="Copy address"
									>
										📋
									</button>
								</div>
							</div>

							<!-- Exchange Rate -->
							<div class="text-xs text-gray-500 dark:text-gray-400">
								{$i18n.t('Exchange rate')}: 1 {invoiceResponse.crypto} = ${invoiceResponse.exchange_rate} USD
							</div>

							<!-- Waiting indicator -->
							<div class="flex items-center justify-center gap-2 py-4">
								<div class="flex gap-1">
									<span class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
									<span class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
									<span class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
								</div>
								<span class="text-sm text-gray-500 dark:text-gray-400">
									{$i18n.t('Waiting for payment...')}
								</span>
							</div>

							<p class="text-xs text-center text-gray-400 dark:text-gray-600">
								{$i18n.t('XRP typically confirms in ~4 seconds')}
							</p>

							<!-- Cancel Button -->
							<div class="pt-2">
								<button
									class="w-full py-2.5 px-4 rounded-xl text-sm font-medium text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition"
									on:click={handleCancel}
								>
									{$i18n.t('Cancel payment')}
								</button>
							</div>
						</div>
					{:else if invoiceStatus?.status === 'confirmed'}
						<div class="p-8 text-center">
							<div class="text-4xl mb-4">✅</div>
							<h3 class="text-lg font-semibold text-green-600 dark:text-green-400">
								{$i18n.t('Payment Confirmed!')}
							</h3>
							<p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
								{$i18n.t('Your subscription is now active.')}
							</p>
							<button
								class="mt-6 px-6 py-2.5 rounded-xl text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 transition"
								on:click={() => goto('/')}
							>
								{$i18n.t('Start chatting')}
							</button>
						</div>
					{:else}
						<div class="p-8 text-center">
							<div class="text-4xl mb-4">⏰</div>
							<h3 class="text-lg font-semibold text-red-600 dark:text-red-400">
								{$i18n.t('Invoice Expired')}
							</h3>
							<p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
								{$i18n.t('This invoice has expired. Please create a new one.')}
							</p>
							<button
								class="mt-6 px-6 py-2.5 rounded-xl text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 transition"
								on:click={() => goto('/billing')}
							>
								{$i18n.t('Try again')}
							</button>
						</div>
					{/if}
				</div>
			{:else}
				<div class="flex flex-col items-center justify-center py-20">
					<p class="text-sm text-red-500">{$i18n.t('Failed to create invoice')}</p>
					<button
						class="mt-4 px-6 py-2 rounded-xl text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 transition"
						on:click={() => goto('/billing')}
					>
						{$i18n.t('Back to plans')}
					</button>
				</div>
			{/if}
		</div>
	</div>
</div>

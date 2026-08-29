<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';

	import { WEBUI_NAME, user, config } from '$lib/stores';
	import {
		getSubscriptionPlans,
		getCurrentSubscription,
		type SubscriptionPlan,
		type UserSubscription
	} from '$lib/apis/billing';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import Minus from '$lib/components/icons/Minus.svelte';
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';
	import { showSidebar } from '$lib/stores';

	const i18n = getContext('i18n');

	let loaded = false;
	let plans: SubscriptionPlan[] = [];
	let currentSubscription: UserSubscription | null = null;

	const tierColors: Record<string, string> = {
		free: 'border-gray-300 dark:border-gray-700',
		pro: 'border-blue-500 dark:border-blue-400',
		ultra: 'border-purple-500 dark:border-purple-400'
	};

	const tierBadgeColors: Record<string, string> = {
		free: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
		pro: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
		ultra: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
	};

	const featureList = (plan: SubscriptionPlan) => [
		{ label: 'Available models', value: plan.max_models === -1 ? 'All models' : `${plan.max_models} models` },
		{ label: 'Chat messages/day', value: plan.max_chats_per_day === -1 ? 'Unlimited' : `${plan.max_chats_per_day}` },
		{ label: 'File uploads', value: plan.max_file_uploads === -1 ? 'Unlimited' : `${plan.max_file_uploads}/day` },
		{ label: 'Knowledge bases', value: plan.max_knowledge_bases === -1 ? 'Unlimited' : `${plan.max_knowledge_bases}` },
		{ label: 'Max tokens/chat', value: plan.max_tokens_per_chat === -1 ? 'Unlimited' : plan.max_tokens_per_chat.toLocaleString() },
		{ label: 'Image generation', value: plan.enable_image_generation },
		{ label: 'Code interpreter', value: plan.enable_code_interpreter },
		{ label: 'Web search', value: plan.enable_web_search },
		{ label: 'API access', value: plan.enable_api_access },
		{ label: 'Priority queue', value: plan.priority_queue }
	];

	onMount(async () => {
		try {
			const [plansResult, subResult] = await Promise.all([
				getSubscriptionPlans(localStorage.token),
				getCurrentSubscription(localStorage.token)
			]);
			plans = plansResult;
			currentSubscription = subResult;
		} catch (err) {
			console.error('Failed to load billing data:', err);
			toast.error('Failed to load subscription plans');
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>{$i18n.t('Subscription Plans')} | {$WEBUI_NAME}</title>
</svelte:head>

{#if loaded}
	<div class="flex flex-col w-full h-full overflow-y-auto">
		<!-- Header -->
		<div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-900">
			<div class="flex items-center gap-2">
				<button
					class="md:hidden p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
					on:click={() => showSidebar.set(!$showSidebar)}
				>
					<SidebarIcon className="size-5" />
				</button>
				<h1 class="text-lg font-semibold">{$i18n.t('Subscription Plans')}</h1>
			</div>
			{#if currentSubscription}
				<button
					class="text-sm text-blue-500 hover:text-blue-600 underline"
					on:click={() => goto('/billing/invoices')}
				>
					{$i18n.t('View invoices')}
				</button>
			{/if}
		</div>

		<!-- Plans Grid -->
		<div class="flex-1 p-4 md:p-8">
			<div class="max-w-5xl mx-auto">
				<p class="text-center text-sm text-gray-500 dark:text-gray-400 mb-8">
					{$i18n.t('Choose the plan that best fits your needs. Pay with crypto via XRP.')}
				</p>

				<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
					{#each plans as plan}
						{@const isCurrentPlan = currentSubscription?.plan_id === plan.id}
						{@const features = featureList(plan)}
						<div
							class="relative flex flex-col rounded-2xl border-2 {tierColors[plan.id] || tierColors.free} {isCurrentPlan
								? 'ring-2 ring-blue-500 dark:ring-blue-400'
								: ''} bg-white dark:bg-gray-900 shadow-sm"
						>
							{#if isCurrentPlan}
								<div class="absolute -top-3 left-1/2 -translate-x-1/2">
									<span
										class="px-3 py-1 text-xs font-medium rounded-full bg-blue-500 text-white"
									>
										{$i18n.t('Current Plan')}
									</span>
								</div>
							{/if}

							<!-- Plan Header -->
							<div class="p-6 text-center">
								<span
									class="inline-block px-3 py-1 text-xs font-medium rounded-full {tierBadgeColors[plan.id] || tierBadgeColors.free}"
								>
									{plan.name}
								</span>
								<div class="mt-4">
									{#if plan.price_usd === 0}
										<span class="text-3xl font-bold">{$i18n.t('Free')}</span>
									{:else}
										<span class="text-3xl font-bold">${plan.price_usd}</span>
										<span class="text-sm text-gray-500 dark:text-gray-400">
											/{$i18n.t('month')}
										</span>
									{/if}
								</div>
								{#if plan.description}
									<p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
										{plan.description}
									</p>
								{/if}
							</div>

							<!-- Features -->
							<div class="flex-1 px-6 pb-4">
								<ul class="space-y-2">
									{#each features as feature}
										<li class="flex items-center gap-2 text-sm">
											{#if typeof feature.value === 'boolean'}
												{#if feature.value}
													<Check className="size-4 text-green-500 shrink-0" />
												{:else}
													<Minus className="size-4 text-gray-300 dark:text-gray-600 shrink-0" />
												{/if}
												<span class={feature.value ? '' : 'text-gray-400 dark:text-gray-600'}>
													{feature.label}
												</span>
											{:else}
												<Check className="size-4 text-green-500 shrink-0" />
												<span>{feature.label}: <strong>{feature.value}</strong></span>
											{/if}
										</li>
									{/each}
								</ul>
							</div>

							<!-- CTA -->
							<div class="p-6 pt-2">
								{#if isCurrentPlan}
									<button
										class="w-full py-2.5 px-4 rounded-xl text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-500 cursor-default"
										disabled
									>
										{$i18n.t('Current Plan')}
									</button>
								{:else if plan.price_usd === 0}
									<button
										class="w-full py-2.5 px-4 rounded-xl text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition"
										on:click={() => goto('/billing/manage')}
									>
										{$i18n.t('Downgrade to Free')}
									</button>
								{:else}
									<button
										class="w-full py-2.5 px-4 rounded-xl text-sm font-medium text-white {plan.id === 'ultra'
											? 'bg-purple-600 hover:bg-purple-700'
											: 'bg-blue-600 hover:bg-blue-700'} transition"
										on:click={() => goto(`/billing/checkout?plan=${plan.id}`)}
									>
										{$i18n.t('Subscribe with XRP')}
									</button>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</div>
{:else}
	<div class="flex items-center justify-center h-full">
		<Spinner />
	</div>
{/if}

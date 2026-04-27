<script lang="ts">
	import { marked } from "marked";
	import { onMount } from "svelte";

	type ContradictionPair = {
		sentence_a: string;
		sentence_b: string;
		explanation: string;
		contradiction_type?: string;
		nli_score?: number | null;
	};

	type CandidatePair = {
		a_id: number;
		b_id: number;
		a_text: string;
		b_text: string;
		score?: number;
		nli_score?: number;
	};

	type RunSummary = {
		run_id: string;
		doc_id: string;
		method: string;
		verifier_model: string;
		pair_count: number;
		total_elapsed: number;
		created_at: number;
		preview: string;
		n_chunks: number;
		n_triples: number;
	};

	type RunDetail = RunSummary & {
		events_json: string;
		document_text: string;
	};

	type Status = "idle" | "scanning" | "done" | "error";
	type Method = "naive" | "cascade";
	type StageStatus = "pending" | "active" | "done";
	type Stage = { label: string; status: StageStatus; detail: string; elapsed?: number };

	const MODELS = [
		"claude-opus-4-7",
		"claude-sonnet-4-6",
		"claude-haiku-4-5",
		"gpt-5.4",
		"gpt-5.4-mini",
	] as const;

	const STAGE_KEYS = ["triples", "ingest", "filter", "nli", "verify"] as const;
	const STAGE_LABELS: Record<(typeof STAGE_KEYS)[number], string> = {
		triples: "Triples",
		ingest: "Ingest",
		filter: "Filter",
		nli: "NLI",
		verify: "Verify",
	};

	let documentText = $state("");
	let model = $state<string>("claude-sonnet-4-6");
	let method = $state<Method>("naive");
	let pairs = $state<ContradictionPair[]>([]);
	let status = $state<Status>("idle");
	let errorMessage = $state("");

	let runs = $state<RunSummary[]>([]);
	let viewingRun = $state<RunDetail | null>(null);
	let viewLoading = $state(false);

	type Verdict = {
		is_contradiction: boolean;
		explanation: string | null;
		contradiction_type: string | null;
		failed: boolean;
	};

	let stages = $state<Record<string, Stage>>(makeStages());
	let stageStarts = $state<Record<string, number>>({});
	let intermediates = $state<{ stage: string; pairs: CandidatePair[] }[]>([]);
	let nliPairs = $state<CandidatePair[]>([]);
	let verdicts = $state<Record<string, Verdict>>({});
	let verifyTotal = $state(0);
	let verifyStep = $state(0);

	let scanStart = $state(0);
	let now = $state(0);
	let timerHandle: ReturnType<typeof setInterval> | undefined;

	function makeStages(): Record<string, Stage> {
		const s: Record<string, Stage> = {};
		for (const k of STAGE_KEYS) s[k] = { label: STAGE_LABELS[k], status: "pending", detail: "" };
		return s;
	}

	function startTimer() {
		now = performance.now();
		if (timerHandle) clearInterval(timerHandle);
		timerHandle = setInterval(() => {
			now = performance.now();
		}, 100);
	}

	function stopTimer() {
		if (timerHandle) {
			clearInterval(timerHandle);
			timerHandle = undefined;
		}
		now = performance.now();
	}

	async function loadRuns() {
		try {
			const res = await fetch("/api/runs");
			if (res.ok) runs = await res.json();
		} catch {
			runs = [];
		}
	}

	onMount(() => {
		loadRuns();
		return () => stopTimer();
	});

	async function deleteRun(run_id: string) {
		await fetch(`/api/runs/${run_id}`, { method: "DELETE" });
		if (viewingRun?.run_id === run_id) {
			viewingRun = null;
			resetMainState();
		}
		await loadRuns();
	}

	async function clearAll() {
		if (!confirm("Delete ALL stored runs and corpus data?")) return;
		await fetch("/api/runs", { method: "DELETE" });
		viewingRun = null;
		resetMainState();
		await loadRuns();
	}

	function resetMainState() {
		pairs = [];
		intermediates = [];
		nliPairs = [];
		verdicts = {};
		verifyTotal = 0;
		verifyStep = 0;
		stages = makeStages();
		stageStarts = {};
		status = "idle";
		errorMessage = "";
		scanStart = 0;
		stopTimer();
	}

	function newScan() {
		viewingRun = null;
		resetMainState();
		documentText = "";
	}

	async function viewRun(summary: RunSummary) {
		if (status === "scanning") return;
		viewLoading = true;
		try {
			const res = await fetch(`/api/runs/${summary.run_id}`);
			if (!res.ok) {
				viewLoading = false;
				return;
			}
			const detail: RunDetail = await res.json();
			viewingRun = detail;
			documentText = detail.document_text || "";
			method = detail.method as Method;
			model = detail.verifier_model;
			resetMainState();
			let events: any[] = [];
			try {
				events = JSON.parse(detail.events_json || "[]");
			} catch {
				events = [];
			}
			for (const ev of events) handleEvent(ev);
			status = "done";
			scanStart = 0;
		} finally {
			viewLoading = false;
		}
	}

	async function submit() {
		const text = documentText.trim();
		if (!text || status === "scanning") return;

		viewingRun = null;
		resetMainState();
		errorMessage = "";
		status = "scanning";
		scanStart = performance.now();
		startTimer();
		if (method === "cascade") {
			stages.triples.status = "active";
			stageStarts.triples = scanStart;
		}

		try {
			const res = await fetch("/api/extract-contradictions", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ document: text, model, method }),
			});
			if (!res.ok || !res.body) {
				status = "error";
				errorMessage = `HTTP ${res.status}`;
				stopTimer();
				return;
			}

			const reader = res.body.getReader();
			const decoder = new TextDecoder();
			let buffer = "";
			let finished = false;

			while (!finished) {
				const { done, value } = await reader.read();
				if (done) break;
				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split("\n");
				buffer = lines.pop() ?? "";

				for (const line of lines) {
					if (!line.startsWith("data: ")) continue;
					const payload = line.slice(6);
					if (payload === "[DONE]") {
						finished = true;
						break;
					}
					try {
						handleEvent(JSON.parse(payload));
					} catch {
						continue;
					}
				}
			}

			if (status === "scanning") status = "done";
			await loadRuns();
		} catch (e) {
			status = "error";
			errorMessage = e instanceof Error ? e.message : "Network error";
		} finally {
			stopTimer();
		}
	}

	function finishStage(key: string, nextKey: string | null) {
		const start = stageStarts[key];
		if (start) stages[key].elapsed = (performance.now() - start) / 1000;
		stages[key].status = "done";
		if (nextKey) {
			stages[nextKey].status = "active";
			stageStarts[nextKey] = performance.now();
		}
	}

	function handleEvent(ev: Record<string, any>) {
		const t = ev.event;
		if (t === "pair") {
			pairs.push({
				sentence_a: ev.sentence_a,
				sentence_b: ev.sentence_b,
				explanation: ev.explanation,
				contradiction_type: ev.contradiction_type,
				nli_score: ev.nli_score,
			});
		} else if (t === "triples") {
			finishStage("triples", "ingest");
			stages.triples.detail = `${ev.triple_count} triples${ev.cached ? " (cached)" : ""}`;
		} else if (t === "ingested") {
			finishStage("ingest", "filter");
			stages.ingest.detail = `${ev.chunks} chunks${ev.cached ? " (cached)" : ""}`;
		} else if (t === "candidates") {
			intermediates.push({ stage: ev.stage, pairs: ev.pairs });
			if (ev.stage === "union") {
				finishStage("filter", "nli");
				stages.filter.detail = `${ev.pairs.length} pairs`;
			}
		} else if (t === "nli_scored") {
			const start = stageStarts.nli;
			if (start) stages.nli.elapsed = (performance.now() - start) / 1000;
			stages.nli.status = "done";
			stages.nli.detail = `${ev.pairs_above_threshold.length} above threshold`;
			nliPairs = ev.pairs_above_threshold;
			verifyTotal = ev.pairs_above_threshold.length;
			if (verifyTotal === 0) {
				stages.verify.status = "done";
				stages.verify.detail = "skipped";
			} else {
				stages.verify.status = "active";
				stageStarts.verify = performance.now();
			}
		} else if (t === "verifier_step") {
			verifyStep = ev.index;
			stages.verify.detail = `${verifyStep}/${ev.total}`;
			if (ev.a_id !== undefined && ev.b_id !== undefined) {
				verdicts[`${ev.a_id}_${ev.b_id}`] = {
					is_contradiction: !!ev.is_contradiction,
					explanation: ev.explanation ?? null,
					contradiction_type: ev.contradiction_type ?? null,
					failed: !!ev.failed,
				};
			}
			if (verifyStep === ev.total) {
				const start = stageStarts.verify;
				if (start) stages.verify.elapsed = (performance.now() - start) / 1000;
				stages.verify.status = "done";
			}
		} else if (t === "error") {
			status = "error";
			errorMessage = ev.message;
		}
	}

	function liveElapsed(k: string): string {
		const s = stages[k];
		if (s.elapsed !== undefined) return `${s.elapsed.toFixed(1)}s`;
		const start = stageStarts[k];
		if (start && s.status === "active") return `${((now - start) / 1000).toFixed(1)}s`;
		return "";
	}

	function totalElapsed(): string {
		if (viewingRun) return `${viewingRun.total_elapsed.toFixed(1)}s`;
		if (scanStart === 0) return "";
		return ((now - scanStart) / 1000).toFixed(1) + "s";
	}

	function statusText(): string {
		if (viewingRun) {
			const n = pairs.length;
			return `Past run · ${n} pair${n === 1 ? "" : "s"} · ${totalElapsed()}`;
		}
		const elapsedStr = scanStart > 0 ? ` ${totalElapsed()}` : "";
		if (status === "idle") return "Ready";
		if (status === "scanning") {
			const n = pairs.length;
			return `Scanning${elapsedStr} - ${n} pair${n === 1 ? "" : "s"}`;
		}
		if (status === "done") {
			const n = pairs.length;
			if (n === 0) return `No contradictions found${elapsedStr}`;
			return `Done${elapsedStr} - ${n} pair${n === 1 ? "" : "s"} found`;
		}
		return `Error: ${errorMessage}`;
	}

	function md(text: string): string {
		return marked.parse(text, { async: false }) as string;
	}

	function stageColor(s: StageStatus): string {
		if (s === "done") return "bg-emerald-500/20 text-emerald-100 border-emerald-400";
		if (s === "active") return "bg-blue-500/25 text-blue-100 border-blue-400 animate-pulse";
		return "bg-zinc-800 text-white/70 border-zinc-600";
	}

	function typeColor(t: string | null | undefined): string {
		switch (t) {
			case "negation": return "border-rose-400 bg-rose-500/15 text-rose-100";
			case "numerical": return "border-amber-400 bg-amber-500/15 text-amber-100";
			case "antonymic": return "border-violet-400 bg-violet-500/15 text-violet-100";
			case "factual": return "border-sky-400 bg-sky-500/15 text-sky-100";
			case "structural": return "border-indigo-400 bg-indigo-500/15 text-indigo-100";
			default: return "border-zinc-500 bg-zinc-800 text-white";
		}
	}

	function timeAgo(ts: number): string {
		const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
		if (s < 60) return `${s}s ago`;
		const m = Math.floor(s / 60);
		if (m < 60) return `${m}m ago`;
		const h = Math.floor(m / 60);
		if (h < 24) return `${h}h ago`;
		return `${Math.floor(h / 24)}d ago`;
	}

	function methodBadge(m: string): string {
		return m === "cascade" ? "border-emerald-400 bg-emerald-500/15 text-emerald-100" : "border-blue-400 bg-blue-500/15 text-blue-100";
	}
</script>

<div class="flex h-screen bg-black text-white">
	<aside class="flex w-72 flex-col border-r-2 border-zinc-700 bg-zinc-950">
		<div class="border-b-2 border-zinc-700 p-3">
			<button
				onclick={newScan}
				class="w-full cursor-pointer rounded-lg border-2 border-blue-400 bg-blue-500/15 px-3 py-2 text-sm
					font-bold text-blue-100 transition-all hover:scale-[1.02] hover:bg-blue-500/30
					hover:shadow-lg hover:shadow-blue-500/30 active:scale-100"
			>
				+ New scan
			</button>
		</div>
		<div class="flex-1 overflow-y-auto p-2">
			<div class="mb-2 px-2 text-[11px] font-bold tracking-wide text-white/80 uppercase">
				History ({runs.length})
			</div>
			{#if runs.length === 0}
				<div class="px-2 text-xs text-white/80">No past runs yet.</div>
			{:else}
				<ul class="flex flex-col gap-1">
					{#each runs as r}
						<li
							class="group flex items-stretch gap-1 rounded-lg border-2 transition-all {viewingRun?.run_id ===
							r.run_id
								? 'border-blue-400 bg-blue-500/15 shadow-lg shadow-blue-500/20'
								: 'border-zinc-700 bg-zinc-900 hover:border-blue-400 hover:bg-zinc-800 hover:shadow-md hover:shadow-blue-500/10'}"
						>
							<button
								onclick={() => viewRun(r)}
								class="min-w-0 flex-1 cursor-pointer px-3 py-2 text-left"
							>
								<div class="truncate text-xs font-semibold text-white">{r.preview || r.doc_id}</div>
								<div class="mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
									<span class="rounded border-2 px-1.5 py-px font-bold {methodBadge(r.method)}">
										{r.method}
									</span>
									<span class="font-bold text-emerald-200">
										{r.pair_count} pair{r.pair_count === 1 ? "" : "s"}
									</span>
									<span class="text-white/80">·</span>
									<span class="font-mono font-semibold text-white">{r.total_elapsed.toFixed(1)}s</span>
								</div>
								<div class="mt-1 text-[11px] text-white/80">
									{r.verifier_model} · {timeAgo(r.created_at)}
								</div>
							</button>
							<button
								onclick={() => deleteRun(r.run_id)}
								aria-label="Delete run"
								class="flex cursor-pointer items-center self-stretch rounded-md px-2 text-[11px]
									font-bold text-white/80 opacity-0 transition-all hover:bg-rose-500/30
									hover:text-rose-100 group-hover:opacity-100"
							>
								X
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
		{#if runs.length > 0}
			<div class="border-t-2 border-zinc-700 p-3">
				<button
					onclick={clearAll}
					class="w-full cursor-pointer rounded-lg border-2 border-rose-400 bg-zinc-900 px-3 py-1.5 text-xs
						font-bold text-rose-100 transition-all hover:bg-rose-500/20 hover:shadow-md hover:shadow-rose-500/20"
				>
					Clear all
				</button>
			</div>
		{/if}
	</aside>

	<div class="flex flex-1 flex-col overflow-hidden">
		<header class="flex items-center justify-between border-b-2 border-zinc-700 bg-zinc-950 px-6 py-4">
			<h1 class="text-lg font-bold text-white">Contradiction Extractor</h1>
		</header>

		<div class="flex-1 overflow-y-auto px-4 py-6">
			<div class="mx-auto flex max-w-3xl flex-col gap-4">
				{#if viewingRun}
					<div class="rounded-xl border-2 border-blue-400 bg-blue-500/10 p-4">
						<div class="flex items-start justify-between gap-2">
							<div class="min-w-0 flex-1">
								<div class="text-xs font-bold tracking-wide text-blue-100 uppercase">Past run</div>
								<div class="mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
									<span class="rounded border-2 px-1.5 py-px font-bold {methodBadge(viewingRun.method)}">
										{viewingRun.method}
									</span>
									<span class="rounded border-2 border-blue-400 bg-blue-500/10 px-1.5 py-px font-bold text-blue-100">
										{viewingRun.verifier_model}
									</span>
									<span class="font-bold text-emerald-200">{viewingRun.pair_count} pair{viewingRun.pair_count === 1 ? "" : "s"}</span>
									<span class="font-mono font-semibold text-white">{viewingRun.total_elapsed.toFixed(1)}s</span>
									<span class="text-white">·</span>
									<span class="font-medium text-white">{timeAgo(viewingRun.created_at)}</span>
								</div>
							</div>
							<button
								onclick={newScan}
								class="cursor-pointer rounded-md border-2 border-zinc-600 bg-zinc-900 px-2 py-1
									text-xs font-bold text-white transition-all hover:border-blue-400
									hover:bg-zinc-800 hover:shadow-md hover:shadow-blue-500/20"
							>
								Close
							</button>
						</div>
					</div>
				{:else}
					<div class="flex flex-wrap items-center gap-3">
						<div class="flex items-center gap-1 rounded-lg border-2 border-zinc-700 bg-zinc-900 p-1 text-sm">
							<button
								onclick={() => (method = "naive")}
								disabled={status === "scanning"}
								class="cursor-pointer rounded-md px-3 py-1 text-xs font-bold transition-all
									disabled:cursor-not-allowed
									{method === 'naive' ? 'bg-blue-500 text-white shadow-md shadow-blue-500/30' : 'text-white hover:bg-zinc-800'}"
							>
								Naive LLM
							</button>
							<button
								onclick={() => (method = "cascade")}
								disabled={status === "scanning"}
								class="cursor-pointer rounded-md px-3 py-1 text-xs font-bold transition-all
									disabled:cursor-not-allowed
									{method === 'cascade' ? 'bg-blue-500 text-white shadow-md shadow-blue-500/30' : 'text-white hover:bg-zinc-800'}"
							>
								KG Cascade
							</button>
						</div>

						<label class="text-sm font-medium text-white" for="model-select">Model</label>
						<select
							id="model-select"
							bind:value={model}
							disabled={status === "scanning"}
							class="cursor-pointer rounded-lg border-2 border-zinc-700 bg-zinc-900 px-3 py-2 text-sm
								font-medium text-white focus:border-blue-400 focus:ring-1 focus:ring-blue-400
								focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
						>
							{#each MODELS as m}
								<option value={m} class="bg-zinc-900 text-white">{m}</option>
							{/each}
						</select>

						<button
							onclick={submit}
							disabled={status === "scanning" || !documentText.trim()}
							class="ml-auto cursor-pointer rounded-xl bg-blue-500 px-5 py-2.5 text-sm font-bold
								text-white transition-all hover:bg-blue-400 hover:shadow-lg hover:shadow-blue-500/40
								disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-white/60 disabled:shadow-none"
						>
							Find Contradictions
						</button>
					</div>
				{/if}

				<textarea
					bind:value={documentText}
					placeholder="Paste a document to scan for self-contradictions..."
					rows="12"
					readonly={viewingRun !== null}
					disabled={status === "scanning"}
					class="resize-y rounded-xl border-2 border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-white
						placeholder:text-white/50 focus:border-blue-400 focus:ring-1 focus:ring-blue-400
						focus:outline-none disabled:opacity-50 read-only:bg-zinc-950"
				></textarea>

				<div class={status === "error" ? "text-sm font-bold text-rose-200" : "text-sm font-medium text-white"}>
					{statusText()}
				</div>

				{#if (method === "cascade" || (viewingRun && viewingRun.method === "cascade")) && (status === "scanning" || status === "done" || status === "error")}
					<div class="flex flex-wrap items-center gap-2">
						{#each STAGE_KEYS as k, i}
							<div class="flex flex-col rounded-lg border-2 px-3 py-1.5 text-xs {stageColor(stages[k].status)}">
								<div class="font-bold">{stages[k].label}</div>
								{#if stages[k].detail}
									<div class="text-[11px] font-medium">{stages[k].detail}</div>
								{/if}
								{#if liveElapsed(k)}
									<div class="font-mono text-[11px] font-semibold tracking-tight">{liveElapsed(k)}</div>
								{/if}
							</div>
							{#if i < STAGE_KEYS.length - 1}
								<div class="font-bold text-blue-200">{">"}</div>
							{/if}
						{/each}
					</div>
				{/if}

				{#if (method === "cascade" || (viewingRun && viewingRun.method === "cascade")) && intermediates.length > 0}
					<div class="flex flex-col gap-2">
						{#each intermediates as inter}
							<details class="rounded-lg border-2 border-zinc-700 bg-zinc-900 transition-all hover:border-zinc-500">
								<summary class="cursor-pointer px-3 py-2 text-xs font-bold text-white hover:bg-zinc-800/40">
									{inter.stage.charAt(0).toUpperCase() + inter.stage.slice(1)} candidates ({inter.pairs.length})
								</summary>
								<div class="border-t-2 border-zinc-700 px-3 py-2">
									{#if inter.pairs.length === 0}
										<div class="text-xs font-medium text-white">none</div>
									{:else}
										<ul class="flex flex-col gap-1.5">
											{#each inter.pairs as p}
												<li class="rounded border-2 border-zinc-700 bg-zinc-950 p-2 text-xs">
													<div class="text-white">
														<span class="font-bold text-blue-200">A [{p.a_id}]:</span> {p.a_text}
													</div>
													<div class="text-white">
														<span class="font-bold text-rose-200">B [{p.b_id}]:</span> {p.b_text}
													</div>
													{#if p.score !== undefined}
														<div class="font-mono text-emerald-200">cos = {p.score.toFixed(3)}</div>
													{/if}
												</li>
											{/each}
										</ul>
									{/if}
								</div>
							</details>
						{/each}

						{#if nliPairs.length > 0}
							<details class="rounded-lg border-2 border-zinc-700 bg-zinc-900 transition-all hover:border-zinc-500" open>
								<summary class="cursor-pointer px-3 py-2 text-xs font-bold text-white hover:bg-zinc-800/40">
									After NLI &geq; threshold ({nliPairs.length}) - verifier output
								</summary>
								<div class="border-t-2 border-zinc-700 px-3 py-2">
									<ul class="flex flex-col gap-1.5">
										{#each nliPairs as p}
											{@const v = verdicts[`${p.a_id}_${p.b_id}`]}
											<li class="rounded border-2 border-zinc-700 bg-zinc-950 p-2 text-xs">
												<div class="text-white">
													<span class="font-bold text-blue-200">A [{p.a_id}]:</span> {p.a_text}
												</div>
												<div class="text-white">
													<span class="font-bold text-rose-200">B [{p.b_id}]:</span> {p.b_text}
												</div>
												<div class="mt-1 flex flex-wrap items-center gap-1.5">
													{#if p.nli_score !== undefined}
														<span class="font-mono text-emerald-200">NLI = {p.nli_score.toFixed(3)}</span>
													{/if}
													{#if v}
														{#if v.failed}
															<span class="rounded border-2 border-amber-400 bg-amber-500/15 px-1.5 py-px font-bold text-amber-100">
																verifier failed
															</span>
														{:else if v.is_contradiction}
															<span class="rounded border-2 border-emerald-400 bg-emerald-500/20 px-1.5 py-px font-bold text-emerald-100">
																contradiction
															</span>
															{#if v.contradiction_type}
																<span class="rounded border-2 px-1.5 py-px font-bold {typeColor(v.contradiction_type)}">
																	{v.contradiction_type}
																</span>
															{/if}
														{:else}
															<span class="rounded border-2 border-rose-400 bg-rose-500/20 px-1.5 py-px font-bold text-rose-100">
																rejected
															</span>
														{/if}
													{:else}
														<span class="rounded border-2 border-zinc-600 bg-zinc-800 px-1.5 py-px font-bold text-white/80">
															pending
														</span>
													{/if}
												</div>
												{#if v && v.explanation}
													<div class="mt-1 rounded bg-zinc-900 px-2 py-1 text-white">
														<span class="font-bold text-white/80">verifier:</span> {v.explanation}
													</div>
												{/if}
											</li>
										{/each}
									</ul>
								</div>
							</details>
						{/if}
					</div>
				{/if}

				<div class="flex flex-col gap-3">
					{#each pairs as pair, i}
						<div class="rounded-xl border-2 border-zinc-700 bg-zinc-900 p-4 shadow-lg transition-all hover:border-blue-400/60 hover:shadow-blue-500/10">
							<div class="mb-2 flex flex-wrap items-center justify-between gap-2">
								<div class="text-xs font-bold text-blue-200">#{i + 1}</div>
								<div class="flex flex-wrap items-center gap-1">
									{#if pair.contradiction_type}
										<div class="rounded-md border-2 px-2 py-0.5 text-[11px] font-bold {typeColor(pair.contradiction_type)}">
											{pair.contradiction_type}
										</div>
									{/if}
									{#if pair.nli_score !== undefined && pair.nli_score !== null}
										<div class="rounded-md border-2 border-emerald-400 bg-emerald-500/15 px-2 py-0.5 text-[11px] font-bold text-emerald-100">
											NLI {pair.nli_score.toFixed(3)}
										</div>
									{/if}
								</div>
							</div>
							<div class="mb-2 border-l-4 border-blue-400 pl-3">
								<div class="prose prose-sm prose-invert max-w-none text-white">
									{@html md(pair.sentence_a)}
								</div>
							</div>
							<div class="mb-3 border-l-4 border-rose-400 pl-3">
								<div class="prose prose-sm prose-invert max-w-none text-white">
									{@html md(pair.sentence_b)}
								</div>
							</div>
							<div class="prose prose-sm prose-invert max-w-none border-t-2 border-zinc-700 pt-2 text-white">
								{@html md(pair.explanation)}
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</div>
</div>

<script lang="ts">
	import { marked } from "marked";

	type ContradictionPair = {
		sentence_a: string;
		sentence_b: string;
		explanation: string;
	};

	type Status = "idle" | "scanning" | "done" | "error";

	const MODELS = [
		"claude-opus-4-7",
		"claude-sonnet-4-6",
		"claude-haiku-4-5",
		"gpt-5.4",
		"gpt-5.4-mini",
	] as const;

	let documentText = $state("");
	let model = $state<string>("claude-sonnet-4-6");
	let pairs = $state<ContradictionPair[]>([]);
	let status = $state<Status>("idle");
	let errorMessage = $state("");

	async function submit() {
		const text = documentText.trim();
		if (!text || status === "scanning") return;

		pairs = [];
		errorMessage = "";
		status = "scanning";

		try {
			const res = await fetch("/api/extract-contradictions", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ document: text, model }),
			});

			if (!res.ok || !res.body) {
				status = "error";
				errorMessage = `HTTP ${res.status}`;
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
					let parsed: { sentence_a?: string; sentence_b?: string; explanation?: string; error?: string };
					try {
						parsed = JSON.parse(payload);
					} catch {
						continue;
					}
					if (parsed.error) {
						status = "error";
						errorMessage = parsed.error;
					} else if (parsed.sentence_a && parsed.sentence_b && parsed.explanation) {
						pairs.push({
							sentence_a: parsed.sentence_a,
							sentence_b: parsed.sentence_b,
							explanation: parsed.explanation,
						});
					}
				}
			}

			if (status === "scanning") status = "done";
		} catch (e) {
			status = "error";
			errorMessage = e instanceof Error ? e.message : "Network error";
		}
	}

	function statusText(): string {
		if (status === "idle") return "Idle";
		if (status === "scanning") {
			const n = pairs.length;
			return `Scanning... ${n} pair${n === 1 ? "" : "s"}`;
		}
		if (status === "done") {
			const n = pairs.length;
			if (n === 0) return "No contradictions found";
			return `Done - ${n} pair${n === 1 ? "" : "s"} found`;
		}
		return `Error: ${errorMessage}`;
	}

	function md(text: string): string {
		return marked.parse(text, { async: false }) as string;
	}
</script>

<div class="flex h-screen flex-col bg-gray-50">
	<header class="border-b border-gray-200 bg-white px-6 py-4">
		<h1 class="text-lg font-semibold text-gray-800">Contradiction Extractor</h1>
	</header>

	<div class="flex-1 overflow-y-auto px-4 py-6">
		<div class="mx-auto flex max-w-3xl flex-col gap-4">
			<div class="flex items-center gap-3">
				<label class="text-sm text-gray-700" for="model-select">Model</label>
				<select
					id="model-select"
					bind:value={model}
					disabled={status === "scanning"}
					class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm
						focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
						disabled:opacity-50"
				>
					{#each MODELS as m}
						<option value={m}>{m}</option>
					{/each}
				</select>
				<button
					onclick={submit}
					disabled={status === "scanning" || !documentText.trim()}
					class="ml-auto rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white
						transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
				>
					Find Contradictions
				</button>
			</div>

			<textarea
				bind:value={documentText}
				placeholder="Paste a document to scan for self-contradictions..."
				rows="12"
				disabled={status === "scanning"}
				class="resize-y rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm
					focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
					disabled:opacity-50"
			></textarea>

			<div class={status === "error" ? "text-sm text-red-600" : "text-sm text-gray-500"}>
				{statusText()}
			</div>

			<div class="flex flex-col gap-3">
				{#each pairs as pair, i}
					<div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
						<div class="mb-2 text-xs font-semibold text-gray-400">#{i + 1}</div>
						<div class="mb-2 border-l-4 border-blue-400 pl-3">
							<div class="prose prose-sm max-w-none">
								{@html md(pair.sentence_a)}
							</div>
						</div>
						<div class="mb-3 border-l-4 border-rose-400 pl-3">
							<div class="prose prose-sm max-w-none">
								{@html md(pair.sentence_b)}
							</div>
						</div>
						<div class="prose prose-sm max-w-none border-t border-gray-100 pt-2 text-gray-700">
							{@html md(pair.explanation)}
						</div>
					</div>
				{/each}
			</div>
		</div>
	</div>
</div>

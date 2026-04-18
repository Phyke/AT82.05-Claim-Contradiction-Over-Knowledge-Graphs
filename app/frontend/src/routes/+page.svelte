<script lang="ts">
	import { marked } from "marked";

	type Message = {
		role: "user" | "assistant";
		content: string;
	};

	let messages: Message[] = $state([]);
	let input = $state("");
	let streaming = $state(false);
	let chatContainer: HTMLDivElement | undefined = $state();

	function scrollToBottom() {
		if (chatContainer) {
			chatContainer.scrollTop = chatContainer.scrollHeight;
		}
	}

	async function send() {
		const text = input.trim();
		if (!text || streaming) return;

		messages.push({ role: "user", content: text });
		input = "";
		streaming = true;

		messages.push({ role: "assistant", content: "" });
		const assistantIdx = messages.length - 1;

		try {
			const res = await fetch("/api/chat", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ message: text }),
			});

			const reader = res.body!.getReader();
			const decoder = new TextDecoder();
			let buffer = "";

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split("\n");
				buffer = lines.pop() ?? "";

				for (const line of lines) {
					if (!line.startsWith("data: ")) continue;
					const payload = line.slice(6);
					if (payload === "[DONE]") break;
					const parsed = JSON.parse(payload);
					messages[assistantIdx].content += parsed.token;
				}
				scrollToBottom();
			}
		} catch {
			messages[assistantIdx].content = "Error connecting to server.";
		} finally {
			streaming = false;
			scrollToBottom();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			send();
		}
	}

	function renderMarkdown(text: string): string {
		return marked.parse(text, { async: false }) as string;
	}
</script>

<div class="flex h-screen flex-col bg-gray-50">
	<!-- Header -->
	<header class="border-b border-gray-200 bg-white px-6 py-4">
		<h1 class="text-lg font-semibold text-gray-800">KG Claim Checker</h1>
	</header>

	<!-- Messages -->
	<div bind:this={chatContainer} class="flex-1 overflow-y-auto px-4 py-6">
		<div class="mx-auto flex max-w-3xl flex-col gap-4">
			{#if messages.length === 0}
				<div class="py-20 text-center text-sm text-gray-400">
					Enter a claim to check against the knowledge graph.
				</div>
			{/if}

			{#each messages as msg}
				<div
					class={msg.role === "user"
						? "self-end rounded-2xl bg-blue-600 px-4 py-2.5 text-white max-w-[80%]"
						: "self-start rounded-2xl bg-white border border-gray-200 px-4 py-2.5 max-w-[80%] shadow-sm"}
				>
					{#if msg.role === "assistant"}
						<div class="prose prose-sm max-w-none">
							{@html renderMarkdown(msg.content)}
						</div>
					{:else}
						<p class="whitespace-pre-wrap text-sm">{msg.content}</p>
					{/if}
				</div>
			{/each}

			{#if streaming}
				<div class="self-start text-xs text-gray-400">Thinking...</div>
			{/if}
		</div>
	</div>

	<!-- Input -->
	<div class="border-t border-gray-200 bg-white px-4 py-3">
		<div class="mx-auto flex max-w-3xl gap-2">
			<textarea
				bind:value={input}
				onkeydown={handleKeydown}
				placeholder="Type a claim to verify..."
				rows="1"
				disabled={streaming}
				class="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm
					focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
					disabled:opacity-50"
			></textarea>
			<button
				onclick={send}
				disabled={streaming || !input.trim()}
				class="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white
					hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
			>
				Send
			</button>
		</div>
	</div>
</div>

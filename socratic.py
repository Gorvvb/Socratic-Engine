import re
from groq import Groq

from config import GROQ_API_KEY, REASONING_MODEL, CONTEXT_WINDOW, MODES
from dialogue import Session, Move, MOVE_LABELS

# System prompts - one per mode
BASE_RULES = """
You are a Socratic dialogue engine. Your purpose is not to win arguments
but to help the user examine their thinking as rigorously as possible.

Rules:
- Be concise. One focused challenge per response - never a list of questions.
- Do not lecture or give long explanations. Ask and probe.
- Never reveal which "move" you are making - just make it naturally.
- If the user concedes a point, acknowledge it briefly and move to the next weakness.
- Never agree with the thesis just to be polite. If it withstands scrutiny, say so explicitly.
- Ground every challenge in logic or evidence - no rhetorical tricks.
"""

MODE_PROMPTS = {
    "gentle": BASE_RULES + """
Tone: Warm and curious. You are a thoughtful friend helping someone think more clearly.
You ask open questions. You don't push hard on any single point.
Acknowledge what is strong in their position before probing what is weak.
""",

    "rigorous": BASE_RULES + """
Tone: Academic and precise. You are a philosopher demanding logical rigour.
You require exact definitions. You reject vague terms.
You trace implications mercilessly but fairly.
You are not hostile - you are exacting.
""",

    "adversarial": BASE_RULES + """
Tone: Direct and unsparing. You are a skilled debater stress-testing this position.
You argue the strongest possible opposing view.
You do not soften challenges. You find the weakest link and attack it.
You acknowledge concessions briefly and immediately find the next vulnerability.
""",
}

# Move selection
MOVE_SELECTOR_PROMPT = """Given a thesis and dialogue history, choose the single most 
effective Socratic move to make next.

Available moves:
  clarify        - a key term is still vague or undefined
  assumption     - an important hidden premise hasn't been surfaced yet
  counterexample - a concrete case exists that challenges the claim
  evidence       - the user hasn't addressed what would falsify the claim
  implication    - following the logic leads somewhere the user may not accept
  steelman       - the opposing view hasn't been seriously engaged with

Avoid repeating a move that was just used unless it is clearly the best option.
Return ONLY the move name, nothing else. One word."""

MOVE_INSTRUCTIONS = {
    "clarify":
        "Make a clarification challenge. Identify the single most important vague or ambiguous "
        "term in the thesis or the user's last response and demand a precise definition.",

    "assumption":
        "Surface one hidden assumption. Find a premise the user is taking for granted "
        "that they haven't stated explicitly. Ask whether it's actually true.",

    "counterexample":
        "Produce one concrete counterexample - a specific case, historical event, or "
        "scenario that, if true, would break or significantly weaken the claim.",

    "evidence":
        "Probe the evidence. Ask what would actually falsify this claim - "
        "what evidence would the user need to see to change their mind?",

    "implication":
        "Trace one logical implication. Follow the claim to a consequence the user "
        "may not have considered or may not be willing to accept.",

    "steelman":
        "Build the strongest version of the opposing position. "
        "Present it as compellingly as you can, then ask the user to respond to it.",
}

# Engine
class SocraticEngine:

	def __init__(self):
		self.client = Groq(api_key=GROQ_API_KEY)

	def _call(self, messages: list[dict], max_tokens: int = 1500) -> str:
		response = self.client.chat.completions.create(
			model=REASONING_MODEL,
			max_tokens=max_tokens,
			messages=messages,
		)
		raw = response.choices[0].message.content
		# Strip complete <think>...</think> blocks
		raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
		# Strip incomplete block if output was cut off before closing tag
		raw = re.sub(r'<think>.*', '', raw, flags=re.DOTALL)
		return raw.strip()

	def _select_move(self, session: Session) -> Move:
		"""Ask the LLM which Socratic move to make next, steering away from recent repeats."""
		history_text = "\n".join(
		f"Engine: {e.challenge}\nUser: {e.response or '[no response yet]'}"
			for e in session.exchanges[-6:]
		)

		recent = session.recently_used_moves(n=4)
		avoid_note = ""
		if recent:
			avoid_note = f"\nRecently used moves (avoid repeating): {', '.join(recent)}"

		prompt = f"""Thesis: "{session.thesis}"

Dialogue so far:
{history_text if history_text else "(no exchanges yet)"}

Moves used so far: {session.used_move_summary()}
Assumptions already surfaced: {', '.join(session.assumptions) if session.assumptions else 'none'}
Points conceded: {len(session.concessions)}{avoid_note}

Which move should come next?"""

		messages = [
			{"role": "system", "content": MOVE_SELECTOR_PROMPT},
			{"role": "user",   "content": prompt},
		]

		raw = self._call(messages, max_tokens=50).lower().strip()

		valid: list[Move] = ["clarify", "assumption", "counterexample", "evidence", "implication", "steelman"]
		for move in valid:
			if move in raw:
				return move
		# Fall back to least recently used move
		used_recently = set(recent)
		for move in valid:
			if move not in used_recently:
				return move
		return "assumption"

	def challenge(self, session: Session, graph_context: str = "") -> tuple[Move, str]:
		move   = self._select_move(session)
		system = MODE_PROMPTS.get(session.mode, MODE_PROMPTS["rigorous"])

		if graph_context:
			system += (
				f"\n\nKnowledge graph facts "
				f"(use these to ground your challenge - prefer them over your own knowledge):\n"
				f"{graph_context}"
			)

		instruction = MOVE_INSTRUCTIONS.get(move, MOVE_INSTRUCTIONS["assumption"])

		messages = [{"role": "system", "content": system}]
		messages.append({
			"role": "user",
			"content": f"I want to examine this claim: \"{session.thesis}\""
		})
		messages.extend(session.history_for_llm(max_exchanges=CONTEXT_WINDOW))
		messages.append({
			"role": "system",
			"content": instruction,
		})

		challenge_text = self._call(messages, max_tokens=1500)
		return move, challenge_text

	def summarise(self, session: Session) -> str:
		cached = session.get_cached_summary()
		if cached:
			return cached

		history_text = "\n".join(
			f"[{MOVE_LABELS[e.move]}] Engine: {e.challenge}\n"
			f"User: {e.response or '[no response]'}"
			+ (" [CONCEDED]" if e.conceded else "")
			for e in session.exchanges
		)

		prompt = f"""A Socratic dialogue has concluded. Here is the full record:

Thesis: "{session.thesis}"
Mode: {session.mode}

{history_text}

Write a diagnostic summary covering:
1. What the user successfully defended
2. What they conceded or failed to defend
3. What remains unresolved
4. An honest verdict: how well does this thesis hold up under scrutiny?

Be precise and fair. This is not praise - it is an honest intellectual assessment."""

		messages = [
			{"role": "system", "content": MODE_PROMPTS.get(session.mode, MODE_PROMPTS["rigorous"])},
			{"role": "user",   "content": prompt},
		]

		result = self._call(messages, max_tokens=1000)
		session.cache_summary(result)
		return result

	def opening_challenge(self, session: Session) -> tuple[Move, str]:
		system = MODE_PROMPTS.get(session.mode, MODE_PROMPTS["rigorous"])

		messages = [
			{"role": "system", "content": system},
			{
				"role":    "user",
				"content": (
					f"I want to examine this claim: \"{session.thesis}\"\n\n"
					f"Begin the Socratic examination. Start by ensuring the thesis is precise "
					f"enough to examine - if any term is vague, demand a definition. "
					f"If it is already precise, make your first substantive challenge."
				)
			}
		]

		challenge_text = self._call(messages, max_tokens=1500)
		return "clarify", challenge_text
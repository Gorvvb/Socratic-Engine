import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeAlias

try:
	from .config import SESSIONS_FILE, DATA_DIR
except ImportError:
	from config import SESSIONS_FILE, DATA_DIR

Move: TypeAlias = Literal["clarify", "assumption", "counterexample", "evidence", "implication", "steelman"]

MOVE_LABELS = {
	"clarify":        "Clarification",
	"assumption":     "Hidden Assumption",
	"counterexample": "Counterexample",
	"evidence":       "Evidence Probe",
	"implication":    "Implication",
	"steelman":       "Steelman",
}


@dataclass
class Exchange:
	move: Move
	challenge: str # what the engine said
	response: str  = "" # what the user replied (empty until they respond)
	conceded: bool = False # did the user concede this point?


@dataclass
class Session:
	id :           str
	thesis :       str
	mode :         str
	created_at :   str                = field(default_factory=lambda: datetime.now().isoformat())
	exchanges :    list[Exchange]     = field(default_factory=list)
	assumptions :  list[str]          = field(default_factory=list)
	concessions :  list[str]          = field(default_factory=list)

	# Move deduplication
	used_moves:   list[tuple]        = field(default_factory=list)

	# Summary cache
	_cached_summary:       str  = field(default="", repr=False)
	_summary_exchange_count: int = field(default=0, repr=False)

	def add_exchange(self, move: Move, challenge: str) -> Exchange:
		ex = Exchange(move=move, challenge=challenge)
		self.exchanges.append(ex)
		topic = challenge[:60].lower().strip()
		self.used_moves.append((move, topic))
		return ex

	def last_exchange(self) -> Exchange | None:
		return self.exchanges[-1] if self.exchanges else None

	def respond(self, response: str, conceded: bool = False):
		last = self.last_exchange()
		if last:
			last.response = response
			last.conceded = conceded
			if conceded:
				self.concessions.append(last.challenge)

	def recently_used_moves(self, n: int = 4) -> list[Move]:
		return [m for m, _ in self.used_moves[-n:]]

	def used_move_summary(self) -> str:
		if not self.used_moves:
			return "none"
		counts: dict[str, int] = {}
		for move, _ in self.used_moves:
			counts[move] = counts.get(move, 0) + 1
		return ", ".join(f"{m} ×{c}" for m, c in counts.items())

	def get_cached_summary(self) -> str | None:
		if self._cached_summary and self._summary_exchange_count == len(self.exchanges):
			return self._cached_summary
		return None

	def cache_summary(self, summary: str):
		self._cached_summary = summary
		self._summary_exchange_count = len(self.exchanges)

	def history_for_llm(self, max_exchanges: int = 12) -> list[dict]:
		messages = []
		for ex in self.exchanges[-max_exchanges:]:
			messages.append({
				"role":    "assistant",
				"content": f"[{MOVE_LABELS[ex.move]}]\n{ex.challenge}"
			})
			if ex.response:
				concede_note = " (conceded)" if ex.conceded else ""
				messages.append({
					"role":    "user",
					"content": ex.response + concede_note
				})
		return messages

	def summary(self) -> str:
		total    = len(self.exchanges)
		answered = sum(1 for e in self.exchanges if e.response)
		conceded = len(self.concessions)
		return (
			f"Thesis: {self.thesis}\n"
			f"Mode: {self.mode}\n"
			f"Exchanges: {answered}/{total} answered | {conceded} conceded\n"
			f"Moves used: {self.used_move_summary()}\n"
			f"Started: {self.created_at[:10]}"
		)

	def to_markdown(self) -> str:
		#Export the full session as readable markdown.
		lines = [
			f"# Socratic Dialogue",
			f"",
			f"**Thesis:** {self.thesis}",
			f"**Mode:** {self.mode}",
			f"**Date:** {self.created_at[:10]}",
			f"**Session:** {self.id}",
			f"",
			f"---",
			f"",
		]
		for i, ex in enumerate(self.exchanges, 1):
			label = MOVE_LABELS.get(ex.move, ex.move)
			lines.append(f"## Exchange {i} - {label}")
			lines.append(f"")
			lines.append(f"**Engine:** {ex.challenge}")
			lines.append(f"")
			if ex.response:
				concede = " *(conceded)*" if ex.conceded else ""
				lines.append(f"**You:** {ex.response}{concede}")
			else:
				lines.append(f"**You:** *(no response)*")
			lines.append(f"")

		if self._cached_summary:
			lines += [
				f"---",
				f"",
				f"## Diagnostic Summary",
				f"",
				self._cached_summary,
				f"",
			]

		stats = [
			f"---",
			f"",
			f"## Stats",
			f"",
			f"- Exchanges: {len(self.exchanges)}",
			f"- Concessions: {len(self.concessions)}",
			f"- Moves used: {self.used_move_summary()}",
		]
		lines += stats
		return "\n".join(lines)


class SessionStore:
	def __init__(self, sessions_file=None):
		self.sessions_file = sessions_file or SESSIONS_FILE
		DATA_DIR.mkdir(exist_ok=True)
		self._sessions: dict[str, Session] = {}
		self._load()

	def _load(self):
		if self.sessions_file.exists():
			with open(self.sessions_file, "rb") as f:
				self._sessions = pickle.load(f)

	def _save(self):
		with open(self.sessions_file, "wb") as f:
			pickle.dump(self._sessions, f)

	def new_session(self, thesis: str, mode: str) -> Session:
		sid = datetime.now().strftime("%Y%m%d_%H%M%S")
		session = Session(id=sid, thesis=thesis, mode=mode)
		self._sessions[sid] = session
		self._save()
		return session

	def save_session(self, session: Session):
		self._sessions[session.id] = session
		self._save()

	def list_sessions(self) -> list[Session]:
		return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

	def get_session(self, sid: str) -> Session | None:
		return self._sessions.get(sid)

	def delete_session(self, sid: str):
		if sid in self._sessions:
			del self._sessions[sid]
			self._save()
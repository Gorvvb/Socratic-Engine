import sys
import os

api_key = os.getenv("GROQ_API_KEY", "")
if not api_key:
	print("\n[Error] GROQ_API_KEY environment variable is not set.")
	print("Get your free key at: https://console.groq.com")
	sys.exit(1)

from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
	from .config import VERSION, MODES, DEFAULT_MODE, DATA_DIR
	from .dialogue import SessionStore, Session
	from .socratic import SocraticEngine, MOVE_LABELS
except ImportError:
	from config import VERSION, MODES, DEFAULT_MODE, DATA_DIR
	from dialogue import SessionStore, Session
	from socratic import SocraticEngine, MOVE_LABELS

console = Console()

BANNER = f"""
[bold magenta]╔══════════════════════════════════════╗[/bold magenta]
[bold magenta]║         Socratic Engine v{VERSION}         ║[/bold magenta]
[bold magenta]╚══════════════════════════════════════╝[/bold magenta]
Type [bold yellow]help[/bold yellow] for commands.
"""

MODE_COLORS = {
	"gentle": "green",
	"rigorous": "cyan",
	"adversarial": "red",
}


def print_help():
	table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
	table.add_column("Command", style="bold yellow")
	table.add_column("Description")

	commands = [
		("new <thesis>",    "Start a new Socratic dialogue on a claim or decision"),
		("respond <text>",  "Respond to the current challenge"),
		("concede",         "Concede the current point and get the next challenge"),
		("next",            "Skip responding and get the next challenge"),
		("summarise",       "Diagnostic summary (cached until new exchanges added)"),
		("export",          "Save the full session as a markdown file"),
		("mode <n>",        "Switch mode: gentle / rigorous / adversarial"),
		("sessions",        "List all saved sessions"),
		("resume <id>",     "Resume a past session by ID"),
		("delete <id>",     "Delete a saved session"),
		("status",          "Show current session info"),
		("help",            "Show this help"),
		("quit / exit",     "Exit"),
	]
	for cmd, desc in commands:
		table.add_row(cmd, desc)

	console.print(Panel(table, title="Commands", border_style="magenta"))
	console.print(f"\n[dim]Modes: {' | '.join(f'[bold]{m}[/bold] - {d}' for m, d in MODES.items())}[/dim]\n")

def print_challenge(move: str, text: str, mode: str):
	color = MODE_COLORS.get(mode, "cyan")
	label = MOVE_LABELS.get(move, move)
	console.print(Panel(
		text,
		title=f"[{color}]{label}[/{color}]",
		border_style=color,
	))

def print_sessions(store: SessionStore):
	sessions = store.list_sessions()
	if not sessions:
		console.print("[yellow]No saved sessions.[/yellow]")
		return

	table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
	table.add_column("ID", style="dim")
	table.add_column("Thesis")
	table.add_column("Mode", style="bold")
	table.add_column("Exchanges")
	table.add_column("Date")

	for s in sessions[:15]:
		table.add_row(
			s.id,
			s.thesis[:60] + ("..." if len(s.thesis) > 60 else ""),
			s.mode,
			str(len(s.exchanges)),
			s.created_at[:10],
		)
	console.print(Panel(table, title="Saved Sessions", border_style="magenta"))

def _do_challenge(engine: SocraticEngine, session: Session, store: SessionStore):
	move, challenge = engine.challenge(session)
	if not challenge:
		console.print("[yellow]Engine returned an empty response - try 'next' to retry.[/yellow]")
		return
	session.add_exchange(move, challenge)
	store.save_session(session)
	print_challenge(move, challenge, session.mode)

def _export_session(session: Session) -> str:
	# Write session to markdown file, returns the path.
	exports_dir = DATA_DIR / "exports"
	exports_dir.mkdir(exist_ok=True)
	filename = f"session_{session.id}.md"
	path = exports_dir / filename
	path.write_text(session.to_markdown(), encoding="utf-8")
	return str(path)

def main():
	DATA_DIR.mkdir(exist_ok=True)
	console.print(BANNER)

	store = SessionStore()
	engine = SocraticEngine()
	session : Session | None = None
	current_mode = DEFAULT_MODE

	while True:
		try:
			prompt_mode = f"[{MODE_COLORS.get(session.mode, 'cyan')}]{session.mode}[/]" if session else "no session"
			raw = console.input(f"[bold magenta]({prompt_mode}) > [/bold magenta]").strip()
		except (EOFError, KeyboardInterrupt):
			console.print("\n[yellow]Goodbye.[/yellow]")
			break

		if not raw:
			continue

		parts = raw.split(None, 1)
		cmd   = parts[0].lower()
		rest  = parts[1].strip() if len(parts) > 1 else ""

		# Commands
		if cmd in ("quit", "exit", "q"):
			console.print("[yellow]Goodbye.[/yellow]")
			break

		elif cmd == "help":
			print_help()

		elif cmd == "new":
			if not rest:
				console.print("[red]Usage: new <your thesis or claim>[/red]")
				console.print('[dim]Example: new "Democracy is the best form of government"[/dim]')
			else:
				thesis   = rest.strip('"\'')
				mode     = session.mode if session else current_mode
				session  = store.new_session(thesis=thesis, mode=mode)
				console.print(f"\n[bold]Examining:[/bold] {thesis}")
				console.print(f"[dim]Mode: {mode} | Session: {session.id}[/dim]\n")

				move, challenge = engine.opening_challenge(session)
				if not challenge:
					console.print("[yellow]Engine returned an empty opening - try 'next' to start.[/yellow]")
				else:
					session.add_exchange(move, challenge)
					store.save_session(session)
					print_challenge(move, challenge, mode)

		elif cmd == "respond":
			if not session:
				console.print("[red]No active session. Use 'new <thesis>' to start one.[/red]")
			elif not rest:
				console.print("[red]Usage: respond <your response>[/red]")
			else:
				last = session.last_exchange()
				if not last:
					console.print("[yellow]No challenge to respond to yet.[/yellow]")
				elif last.response:
					console.print("[yellow]Already responded. Use 'next' to get the next challenge.[/yellow]")
				else:
					session.respond(rest, conceded=False)
					store.save_session(session)
					_do_challenge(engine, session, store)

		elif cmd == "concede":
			if not session:
				console.print("[red]No active session.[/red]")
			else:
				last = session.last_exchange()
				if not last:
					console.print("[yellow]Nothing to concede yet.[/yellow]")
				else:
					session.respond("[conceded]", conceded=True)
					store.save_session(session)
					console.print("[dim]Point conceded. Moving on...[/dim]\n")
					_do_challenge(engine, session, store)

		elif cmd == "next":
			if not session:
				console.print("[red]No active session.[/red]")
			else:
				_do_challenge(engine, session, store)

		elif cmd == "summarise":
			if not session:
				console.print("[red]No active session.[/red]")
			elif len(session.exchanges) < 2:
				console.print("[yellow]Not enough exchanges to summarise yet.[/yellow]")
			else:
				cached = session.get_cached_summary()
				if cached:
					console.print("[dim]Showing cached summary - no new exchanges since last time.[/dim]")
				else:
					console.print("[dim]Generating summary...[/dim]")
				summary = engine.summarise(session)
				store.save_session(session)
				console.print(Panel(summary, title="Diagnostic Summary", border_style="magenta"))

		elif cmd == "export":
			if not session:
				console.print("[red]No active session.[/red]")
			elif not session.exchanges:
				console.print("[yellow]Nothing to export yet.[/yellow]")
			else:
				# Make sure summary is cached before exporting if we have enough exchanges
				if len(session.exchanges) >= 2 and not session.get_cached_summary():
					console.print("[dim]Generating summary for export...[/dim]")
					engine.summarise(session)
				path = _export_session(session)
				store.save_session(session)
				console.print(f"[green]Session exported to:[/green] {path}")

		elif cmd == "mode":
			if not rest or rest not in MODES:
				console.print(f"[red]Available modes: {', '.join(MODES.keys())}[/red]")
				for m, desc in MODES.items():
					console.print(f"  [bold]{m}[/bold] - {desc}")
			else:
				current_mode = rest
				if session:
					session.mode = rest
					store.save_session(session)
				console.print(f"[green]Mode set to:[/green] {rest}")

		elif cmd == "status":
			if not session:
				console.print("[yellow]No active session.[/yellow]")
			else:
				console.print(Panel(session.summary(), title="Session Status", border_style="cyan"))

		elif cmd == "sessions":
			print_sessions(store)

		elif cmd == "resume":
			if not rest:
				console.print("[red]Usage: resume <session_id>[/red]")
				print_sessions(store)
			else:
				s = store.get_session(rest)
				if not s:
					console.print(f"[red]Session '{rest}' not found.[/red]")
				else:
					session = s
					console.print(f"[green]Resumed session:[/green] {session.id}")
					console.print(Panel(session.summary(), border_style="cyan"))
					last = session.last_exchange()
					if last and not last.response:
						console.print("\n[dim]Last unanswered challenge:[/dim]")
						print_challenge(last.move, last.challenge, session.mode)

		elif cmd == "delete":
			if not rest:
				console.print("[red]Usage: delete <session_id>[/red]")
			else:
				confirm = console.input(f"[red]Delete session '{rest}'? (yes/no): [/red]").strip().lower()
				if confirm == "yes":
					store.delete_session(rest)
					if session and session.id == rest:
						session = None
					console.print("[green]Session deleted.[/green]")
				else:
					console.print("[yellow]Cancelled.[/yellow]")
		else:
			console.print(f"[red]Unknown command: '{cmd}'. Type 'help' for commands.[/red]")

if __name__ == "__main__":
    main()
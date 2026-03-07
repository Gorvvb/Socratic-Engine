# Socratic Engine

It's a dialogue engine that examines your claims and decisions by pretending to be Socrates. You make a statement, and it will find the weakest point and attacks it. You defend, then it finds the next weakness.

The goal isn't actually to win. It's to find out whether your thinking actually holds up.

---

## What does it do?

You give it a claim, a decision, a belief, an argument, or something similar. It runs a structured Socratic examination using six moves, picking the most effective one each time:
- **Clarification**     - demands precise definitions before anything else
- **Hidden Assumption** - surfaces premises you didn't know you were making
- **Counterexample**    - produces a concrete case that breaks your claim
- **Evidence Probe**    - asks what would actually falsify what you're saying
- **Implication**       - follows your logic somewhere you may not want to go
- **Steelman**          - builds the strongest possible opposing view and makes you respond to it

It tracks what moves it has already made, and avoids repeating the same angle twice. Sessions are saved and persist across restarts. At any point you can ask for a summary, and it will tell you how well your claim has held up. The summary is cached so you won't need to pay for it twice.

---

## Modes

- **gentle** - curious and collaborative. Good for exploring ideas you are still forming
- **rigorous** - academic and precise, will demand definitions and logical consistency
- **adversarial** - stress test mode, argues the strongest opposing position without softening

You can switch modes mid-session.

---

## Setup

Requires the same Groq API key as my Knowledge Graph Reasoner.

### Requirements
- Python 3.11+
- A free Groq API key: [console.groq.com](https://console.groq.com)

### Install
```bash
# 1. Clone and enter the project
git clone https://github.com/Gorvvb/Socratic-Engine
cd Socratic-Engine

# 2. Create and activate a virtual python environment
python -m venv venv
venv\Scripts\activate    # Windows
source venv/bin/activate # Linux / Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Groq API key
set GROQ_API_KEY=gsk_your_key_here          # Windows cmd
$env:GROQ_API_KEY = "gsk_your_key_here"     # PowerShell
export GROQ_API_KEY=gsk_your_key_here       # Linux / Mac
# Or set the variable in environment variables

# 5. Run
python cli.py
```

---

## Usage

Start a session with any claim or decision:

```
> new "Social media has made society worse"
> new "I should drop out of university and focus on my own projects"
> new "Consciousness cannot be explained by physical processes alone"
```

The engine opens with a clarification challenge. Respond to it:

```
> respond By worse I mean measurable decline in mental health and political polarisation
```

It picks the next weakest point and attacks. Keep defending:

```
> respond Correlation studies consistently show increased anxiety rates since 2012
```

Give up a point and move on:

```
> concede
```

Skip responding and get the next challenge:

```
> next
```

When you want a verdict:

```
> summarise
```

Save the full session as a markdown file:

```
> export
```

Exports go to `data/exports/` and include the full dialogue and diagnostic summary.

---

### Other commands

```
> mode <n>       - switch mode: gentle / rigorous / adversarial
> status         - see exchanges, concessions, and moves used so far
> sessions       - list all saved sessions
> resume <id>    - pick up a past session
> delete <id>    - delete a saved session
> help           - show all commands
> quit           - exit
```
# Pitch

Feature announce for the Projects tab. The product was already public.

## One-liner

A local board for where your own products stand.

(9 words. The playbook cap is 15.)

The product line on the README stays: "A local start page for what your AI agents did."

## Benefits

- Your own products sit on a board on the same page as the agent log.
- The project you open shows the current state, links, a couple of metrics, and a short timeline.
- The page runs on your machine: loopback only, no analytics, no account.

## 50 words

Agent Worklog is a local start page for what your AI agents did. The Projects tab is a board for your own products. Open one and you see the current state, links, metrics, and a short timeline. It is MIT, it runs on your machine, and it serves loopback only.

## 150 words

Agent Worklog builds a static start page from what your agents did. Claude Code sessions and a JSON log become columns, with waiting items, day groups, and links to files you chose to keep. Python 3.9+ and the standard library build the page.

The Projects tab is the board for your own products. A list sits on the left. The project you open shows where you left off, plus the links, metrics, and timeline rows in the config. Leave projects out and the page uses the built-in list shipped with the repo. Set [[projects]] and that list is the one on the board. The demo log is fictional: Client A, Client B, a newsletter, and a side project.

Run python3 -m worklog demo --serve and open the Projects tab, or use a #project= link. The server binds to loopback only. There is no analytics, no account. The license is MIT.

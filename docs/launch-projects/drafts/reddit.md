# Reddit drafts

Two posts, two days, two wordings. Evan posts and replies. A bot must not submit these.

Read each sub's rules again the day you post. The notes below are from public rules checked on Oct 29, 2026.

Suggested order:

1. Day 0 — r/SideProject (best fit: a maker showing a working local tool and asking one question).
2. Day 1 — r/opensource, flair **Promotional** (best fit: MIT, OSI license, source in the post).

Skipped on purpose:

- r/selfhosted. The server refuses every host except loopback. A post there would describe a deploy path this project does not have.
- r/Python. Showcase posts belong in the monthly showcase thread, and the sub has been pulling AI-tool showcases out of the main feed. Optional only, inside that thread, with the sections the rules name: What My Project Does, Target Audience, Comparison.

## r/SideProject — day 0

Title: I added a Projects board to my local agent work log

I keep a local start page of what my agents did: Claude Code on one side, a JSON log on the other. I still had to remember, separately, where each of my own products stood.

The page now has a Projects tab.

- A list of those products on the left
- The one you open shows the current state in a sentence or two
- Links, a couple of metrics, and a short timeline

It is a static file. Python 3.9+ and the standard library. MIT.

```
python3 -m worklog demo --serve
```

Open http://127.0.0.1:8731/ and choose Projects. `#project=golf-cart-racer` opens one project. The demo clients are made up. The board in that demo is the built-in list that ships with the repo. Your own `[[projects]]` list replaces it.

The server only binds to loopback. There is no hosted copy and no analytics.

Is the card enough (state, links, metrics, timeline), or is a field missing that you would actually use?

Repo: https://github.com/evankrob/agent-worklog

Before posting: reply to comments the same day. Do not paste the r/opensource text here.

## r/opensource — day 1

Flair: Promotional

Title: MIT local dashboard for agent logs, with a Projects board

I maintain a Python tool that builds a start page from agent logs and serves it on 127.0.0.1. The license is MIT. There is no account and no analytics. The generated page sends `no-referrer`, and its content security policy blocks network loads. The server refuses to bind to anything but loopback.

What shipped this week is a Projects board on that same page. Your own products, each with a current-state sentence, links, a couple of metrics, and a short timeline. The README shots are from the fictional demo, not from a client log.

https://github.com/evankrob/agent-worklog

```
python3 -m worklog demo --serve
```

If you have tried local tools that read agent transcripts, I would like to know whether the redaction section of the README is specific enough.

Before posting: this sub treats unedited AI posts as low-effort. Rewrite the draft in your voice. Stay in the thread. MIT is an OSI license, which the sub requires for linked code.

## Answers to likely questions

Use these as notes. Write the reply yourself.

**License?** MIT. See `LICENSE` in the repo.

**Cost?** Free.

**Where do I host it?** On the machine you are using. `serve` accepts `127.0.0.1`, `localhost`, and `::1`, and refuses anything else.

**Does it upload logs?** No. Extractors keep a redacted summary. They do not keep the transcript. There is no analytics, no remote font, and no remote script.

**Is the demo my data?** No. `python3 -m worklog demo` writes a fictional log inside the demo folder and does not read your home directory.

**Can I change the projects?** Yes. `[[projects]]` in the config replaces the built-in list. Leave it out and the built-in list stays. An empty list clears the tab.

**Why are the metrics specific?** They are the values in the built-in list (holes, issue counts, and so on). The screenshots did not add numbers.

# Projects tab — major-feature launch kit

Assets for the Projects tab on [Agent Worklog](https://github.com/evankrob/agent-worklog). This is a major-feature run of Evan's product release playbook. The page behavior is unchanged. Evan posts. Bots do not post to X or Reddit.

The shots are from the fictional demo (`python3 -m worklog demo --serve`), which uses the built-in product list. Client names on the Work tab in the GIF are the demo's Client A and Client B. No extra metrics were added for the pictures.

## What's in here

| Path | What it is |
| --- | --- |
| [screenshots/01-projects-desktop-light.png](screenshots/01-projects-desktop-light.png) | Desktop, light theme. List, current state, links, metrics, timeline. |
| [screenshots/02-projects-desktop-dark.png](screenshots/02-projects-desktop-dark.png) | Same view, dark theme. |
| [screenshots/03-projects-mobile.png](screenshots/03-projects-mobile.png) | Narrow layout, light theme, full board. |
| [gifs/projects-switch.gif](gifs/projects-switch.gif) | 4.8s. Work → Projects (Golf Cart Racer) → What You Missed. |
| [og-image.png](og-image.png) | 1200×630 card. Product name, one-liner, screenshot. |
| [pitch.md](pitch.md) | One-liner, benefits, short and long descriptions. |
| [links.md](links.md) | Repo, demo command, license. No public URL. |
| [drafts/x-variant-a.md](drafts/x-variant-a.md) | X post for Evan, Variant A shape, plus a short reply. |
| [drafts/reddit.md](drafts/reddit.md) | Two different posts, and answers to likely questions. |
| [drafts/rd-blog-outline.md](drafts/rd-blog-outline.md) | Raleigh Digital blog outline, H2s only. |
| [checklist.md](checklist.md) | What is done, and what Evan still does. |
| [replies.md](replies.md) | Empty reply log. Fill it after the posts go out. |

The README at the repo root uses copies of the light desktop shot and the GIF:

- [../preview-projects.png](../preview-projects.png)
- [../preview-projects.gif](../preview-projects.gif)

The older Work preview stays at [../preview.png](../preview.png).

## How the pictures were made

1. `python3 -m worklog demo --dir /tmp/worklog-demo` wrote a fictional demo and built `index.html`.
2. `python3 -m worklog serve -c /tmp/worklog-demo/worklog.toml --port 8731` served it on `127.0.0.1` only.
3. Headless Chrome (the VM's Google Chrome, driven by Playwright) opened that page.
4. Desktop stills are 1280×779 CSS pixels at 2×. Light theme opened `#project=golf-cart-racer`. Dark theme is the same page after clicking **Dark**.
5. The mobile shot is a 390×844 CSS-pixel viewport at 2×, full page, light theme, same project.
6. The GIF is 1100×760 at 1×, 8 frames per second, 38 frames (4.76 seconds). It holds the Work tab, clicks **Projects** (Golf Cart Racer opens), then clicks **What You Missed**. ffmpeg built the GIF with `palettegen` and `paletteuse`. The file is about 237 KB, under the playbook's X size note.

The built-in Agent Worklog card still says the Projects tab is the open pull request. These shots use Golf Cart Racer and What You Missed, so that sentence is not in the hero image. Updating the card is a product change and is not part of this kit.

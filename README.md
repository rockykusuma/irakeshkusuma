# rakesh@matrix — portfolio

A single-file, Matrix-themed personal site for **Rakesh Kusuma** — Lead iOS / BLE engineer.

## What's here
- `index.html` — the entire site (HTML/CSS/JS, no build step): an interactive terminal,
  code-rain background, and a "code → human" video figure that reveals on `whoami`.
- `fal_out/` — three rendered clips (Seedance 2.0) used by the hero: build/approach,
  turn-to-camera, and the looping glance.
- `generate_seedance.py` — the script that generated the clips via the fal.ai API.

## Run
Open `index.html` directly, or serve the folder:

    python3 -m http.server 8000   # then visit http://localhost:8000

## Console commands
Type into the on-page terminal: `help`, `about`, `skills`, `projects`,
`experience`, `contact`, `ls`, `clear`, `sudo hire-me`.

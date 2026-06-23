#!/usr/bin/env python3
"""
Generate the "code -> human" Matrix reveal on fal.ai (Seedance 2.0).

Runs three shots in sequence, feeding each shot's LAST frame into the next so
they cut together seamlessly:

  Shot A  text-to-video   : code figure builds, walks in, forms a suit + sunglasses from code
  Shot B  image-to-video  : figure steps to the RIGHT, turns frontal, settles right-of-frame
  Shot C  image-to-video  : glance LOOP - figure glances left + leans, returns frontal (seamless)

Outputs land in ./fal_out/.

USAGE
  pip install fal-client imageio imageio-ffmpeg requests
  python generate_seedance.py            # runs A, B, C in order
  python generate_seedance.py a          # run only shot A
  python generate_seedance.py b c        # run B then C (reuses existing frames)

Requires FAL_KEY in .env.local (already present in this folder).
Re-running skips any shot whose .mp4 already exists, so you can iterate cheaply.
"""

import os, sys, subprocess, pathlib

# ---------------------------------------------------------------- config
TIER         = "fast"        # "fast" (720p, cheaper) or "standard" (adds 1080p)
RESOLUTION   = "720p"        # "480p" | "720p" | "1080p" (1080p = standard only)
ASPECT       = "16:9"        # "16:9" | "9:16" | "1:1" | "21:9" ...
GEN_AUDIO    = False         # the model can add ambient audio; off for a silent hero loop
DUR_A, DUR_B, DUR_C = "6", "5", "4"   # seconds per shot (4-15)

HERE      = pathlib.Path(__file__).parent.resolve()
OUT       = HERE / "fal_out"

SEG = "fast/" if TIER == "fast" else ""
M_T2V = f"bytedance/seedance-2.0/{SEG}text-to-video"
M_I2V = f"bytedance/seedance-2.0/{SEG}image-to-video"

NEG = ("other colors, red, blue, orange, rainbow, white background, on-screen text, "
       "captions, subtitles, watermark, logo, photorealistic skin, exact facial "
       "likeness, real photograph, distorted face, extra limbs, deformed hands, "
       "jump cuts, stuttering, low detail")

PROMPT_A = (
    "Cinematic 3D shot drifting forward through a pitch-black void filled with "
    "Matrix-style digital rain: dense vertical streams of glowing green katakana, "
    "numerals and code symbols cascading through volumetric 3D space. The camera "
    "glides slowly between the columns of falling code. Deep in the rain, thousands "
    "of green glyphs detach from the streams and swirl inward, assembling "
    "particle-by-particle into a bare, featureless human figure made entirely of "
    "glowing green characters. The code-built figure walks slowly toward the camera "
    "along the z-axis, growing larger and denser with each step. As it approaches, "
    "streams of green code weave across its body and gradually materialize a sharply "
    "tailored professional business suit (blazer and dress shirt) with sleek "
    "sunglasses forming over its eyes, the entire outfit assembling from flowing "
    "green code. Now fully dressed in the green code suit and sunglasses, it takes a "
    "few steps and comes to rest at a three-quarter back angle, still composed of "
    "flowing green code, not yet facing the camera. Rendered exclusively in green "
    "Matrix code on a pure black background, no other colors. Volumetric glow, shallow "
    "depth of field, particle trails, faint CRT scanline flicker, dark moody "
    f"atmosphere. Single continuous smooth camera move, hyper-detailed. Avoid: {NEG}."
)

PROMPT_B = (
    "A human figure made entirely of flowing green Matrix code, wearing a tailored "
    "professional business suit and sleek sunglasses, stands in a pitch-black void, "
    "faint green digital rain falling behind. The figure takes a few slow steps "
    "sideways to the right, then turns to face the camera and comes to rest standing "
    "in the right third of the frame. The left two-thirds of the frame stays open and "
    "empty, with only green code rain falling. As it turns, the streaming green "
    "characters sharpen and settle into the clear silhouette of a man in a "
    "professional suit and sunglasses with short hair and a short beard, rendered "
    "purely as glowing green code, stylized and abstract rather than a photographic "
    "face. The suit and sunglasses stay consistent and clearly defined. Smooth "
    "motion, then hold. The camera stays locked and steady. Rendered exclusively in "
    "green Matrix code on a pure black background, no other colors. Volumetric glow, "
    "shallow depth of field, faint CRT scanline flicker. Hyper-detailed. "
    f"Avoid: {NEG}, centered subject."
)

PROMPT_C = (
    "The green code figure of a man wearing a tailored professional suit and sleek "
    "sunglasses, with short hair and a short beard, stands in the right third of the "
    "frame, facing the camera, in a pitch-black void with faint green digital rain "
    "falling behind him; the left two-thirds of the frame stays open and empty with "
    "only falling green code. He stands rooted to one spot, his body, shoulders, "
    "torso and feet completely still and planted. Only his head turns gently to the "
    "left in a small, slow head tilt, glancing toward the text off-screen on his left, "
    "holds for a brief beat, then his head turns smoothly back to face the camera, "
    "ending in the exact same frontal pose it started in so the motion loops "
    "seamlessly. Nothing else moves: the figure never slides, walks, drifts or shifts "
    "position, and the shoulders and torso do not rotate. Gentle idle shimmer in the "
    "code throughout. The suit and sunglasses stay consistent. Camera locked, "
    "perfectly still. Rendered exclusively in green Matrix code on a pure black "
    "background, no other colors. Subtle CRT scanline flicker, faint volumetric glow. "
    "Smooth, slow, gentle motion. "
    f"Avoid: {NEG}, centered subject, figure sliding, body translating, moving left, "
    "walking, drifting, repositioning, whole body turning, shoulders turning, torso "
    "turning, fast motion, looking right."
)

# ---------------------------------------------------------------- setup
def load_env():
    env = HERE / ".env.local"
    if not env.exists():
        sys.exit("ERROR: .env.local not found next to this script.")
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    if not os.environ.get("FAL_KEY"):
        sys.exit("ERROR: FAL_KEY missing in .env.local")

def deps():
    try:
        import fal_client, imageio_ffmpeg, requests  # noqa
    except ImportError:
        sys.exit("Missing deps. Run:\n  pip install fal-client imageio imageio-ffmpeg requests")

# ---------------------------------------------------------------- helpers
def run_shot(model, args, out_mp4):
    import fal_client, requests
    if out_mp4.exists():
        print(f"  skip (exists): {out_mp4.name}")
        return out_mp4
    print(f"  -> {model}")
    result = fal_client.subscribe(
        model, arguments=args, with_logs=True,
        on_queue_update=lambda u: (
            [print("    ", l["message"]) for l in u.logs]
            if isinstance(u, fal_client.InProgress) and u.logs else None),
    )
    url = result["video"]["url"]
    print(f"  downloading {url}")
    out_mp4.write_bytes(requests.get(url, timeout=300).content)
    print(f"  saved {out_mp4}")
    return out_mp4

def last_frame(mp4, png):
    """Grab the final frame of a clip (bundled ffmpeg, no system install needed)."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-sseof", "-0.2", "-i", str(mp4),
                    "-frames:v", "1", "-q:v", "2", str(png)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png

def upload(path):
    import fal_client
    return fal_client.upload_file(str(path))

def base(dur):
    return {"resolution": RESOLUTION, "duration": dur,
            "aspect_ratio": ASPECT, "generate_audio": GEN_AUDIO}

# ---------------------------------------------------------------- shots
def shot_a():
    print("Shot A - code figure builds & approaches (text-to-video)")
    mp4 = run_shot(M_T2V, {"prompt": PROMPT_A, **base(DUR_A)}, OUT / "shot_a.mp4")
    last_frame(mp4, OUT / "frame_a_last.png")
    return mp4

def shot_b():
    print("Shot B - turn toward camera as a green human silhouette (image-to-video)")
    fa = OUT / "frame_a_last.png"
    if not fa.exists():
        sys.exit("Need Shot A's last frame first. Run shot 'a' before 'b'.")
    args = {"prompt": PROMPT_B,
            "image_url": upload(fa),   # start: green code figure from Shot A
            **base(DUR_B)}
    mp4 = run_shot(M_I2V, args, OUT / "shot_b.mp4")
    last_frame(mp4, OUT / "frame_b_last.png")
    return mp4

def shot_c():
    print("Shot C - hold on portrait (image-to-video)")
    fb = OUT / "frame_b_last.png"
    if not fb.exists():
        sys.exit("Need Shot B's last frame first. Run shot 'b' before 'c'.")
    args = {"prompt": PROMPT_C, "image_url": upload(fb), **base(DUR_C)}
    return run_shot(M_I2V, args, OUT / "shot_c.mp4")

# ---------------------------------------------------------------- main
def main():
    load_env(); deps()
    OUT.mkdir(exist_ok=True)
    want = [a.lower() for a in sys.argv[1:]] or ["a", "b", "c"]
    print(f"Tier={TIER}  res={RESOLUTION}  aspect={ASPECT}  audio={GEN_AUDIO}")
    print(f"Output dir: {OUT}\n")
    steps = {"a": shot_a, "b": shot_b, "c": shot_c}
    for k in want:
        if k in steps:
            steps[k]()
            print()
    print("Done. Clips in ./fal_out/. Stitch A -> B -> C in your editor;")
    print("a ~6-frame cross-dissolve (or one green glitch flash) hides each cut.")

if __name__ == "__main__":
    main()

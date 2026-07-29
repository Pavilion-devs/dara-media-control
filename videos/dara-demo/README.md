# Dara demo video

This is the reproducible HyperFrames source for Dara's narrated judge demo. The
composition is 1920×1080 and 165.929 seconds long, under the three-minute submission
limit.

The project contains 12 local HTML scenes, local production screenshots, generated
narration, captions, and generated sound effects. It has no background music and does
not depend on live provider calls during playback. The final frame points to Dara's
public GitHub repository rather than a session-gated or temporary deployment URL.

## Validate

Requirements: Node.js 22+, FFmpeg, and Chrome.

```bash
npm run check
```

The project pins HyperFrames 0.7.82. The final validation on 2026-07-29 passed its
runtime, layout, motion, and contrast gate with zero errors. Hero-frame contact sheets
were reviewed after the accessibility palette pass. Two non-gating contrast warnings
occur only while scene one's probe copy is being hidden for the verdict handoff; its
held readable state passes.

## Render

Rendering is deliberately not part of repository setup. After final-preview approval:

```bash
npm run render -- --quality high --output dara-demo.mp4
ffprobe -v error -show_format dara-demo.mp4
```

The rendered MP4 must then be watched end to end, confirmed under three minutes, and
uploaded publicly to YouTube before T-46 can be marked complete.

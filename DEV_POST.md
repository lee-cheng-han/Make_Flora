# Make_Flora: A Valentine's Installation That Plays Music When You Show It Flowers

**Botanical Music** — hear the melody of every bloom. For Valentine's, we built an interactive installation that combines computer vision, floriography (the language of flowers), and hardware: show a rose and the speaker plays one tune; show a bouquet and it plays another. A pulsing heart, driven by an op-amp, grows and shrinks with the moment.

---

## The Concept

We wanted something romantic and playful for Valentine's: an experience that feels like flowers *talking* through music. Walk up with a rose, and the system recognizes it and plays a song. A separate ESP32 drives an I2S speaker, and an op-amp circuit controls a heart that pulses — bigger when there's a flower in view, smaller when there isn't.

---

## Architecture

```
┌─────────────────┐     MJPEG stream      ┌──────────────────────┐
│   ESP32-CAM     │ ────────────────────► │  PC (Python server)  │
│   (camera)      │                       │  • Roboflow API      │
└─────────────────┘                       │  • /stream (MJPEG)   │
                                          │  • /detection (JSON) │
                                          └──────────┬───────────┘
                                                     │
                    ┌────────────────────────────────┼────────────────────────────────┐
                    │                                │                                │
                    ▼                                ▼                                ▼
          ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
          │  React frontend  │              │  Speaker ESP32  │              │   Op-amp heart  │
          │  • Video + boxes │              │  • Poll /detect │              │  • Grows/shrinks │
          │  • Floriography  │              │  • I2S audio    │              │  • Analog PWM    │
          │  • Vinyl UI      │              │  • Rose → song1 │              │  • Valentine's   │
          └─────────────────┘              │  • Flower → sng2│              └─────────────────┘
                                           └─────────────────┘
```

- **ESP32-CAM** streams video over WiFi (`http://IP/stream`)
- **PC** runs a Flask server that pulls frames, runs Roboflow detection, draws boxes, and serves MJPEG + a JSON `/detection` endpoint
- **React frontend** shows the stream, bounding boxes, and floriography text in a vinyl-style UI
- **Speaker ESP32** polls `/detection` every 500ms and plays sine-wave melodies via I2S
- **Op-amp heart** responds to a control signal and visually pulses (bigger when flowers are detected, smaller when idle)

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Camera | ESP32-CAM, MJPEG stream |
| Detection | Roboflow serverless workflows (`find-roses`, `find-cluster-of-flowers`) |
| Backend | Python, Flask, OpenCV, MjpegStreamReader |
| Frontend | React, Vite, ReactPlayer (optional) |
| Speaker | ESP32, I2S DAC/amp, sine-wave synthesis |
| Heart | Op-amp circuit, PWM or analog envelope for size |

---

## Flow

1. Point the ESP32-CAM at a flower (or bouquet).
2. PC pulls frames, sends them to Roboflow, gets bounding boxes.
3. Server returns `{ "name": "Rose" }` or `{ "name": "Flower Cluster" }` on `/detection`.
4. Speaker ESP32 polls that endpoint and maps:
   - Rose → song1 (melody)
   - Flower Cluster → song2 (melody)
   - Nothing → silence
5. Frontend shows live video with boxes and floriography text.
6. The op-amp heart grows or shrinks based on detection intensity or a derived control signal.

---

## Floriography

Each detected class has a short story:

- **Rose** — "Roses symbolize love, passion, and beauty. The red rose speaks the language of the heart. In floriography, a single rose means 'I love you still.'"
- **Flower Cluster** — "A gathering of blooms speaks of abundance, joy, and the beauty of nature in full expression."

---

## Challenges & Learnings

- **Speaker static** — HTTP polling was blocking the main loop. Moving detection polling to a FreeRTOS task on another core keeps the audio loop smooth.
- **IP addresses** — ESP32-CAM, PC, and speaker ESP32 must share the same subnet. We set `DETECTION_SERVER` and `CAMERA_SOURCE` to the PC and camera IPs.
- **MJPEG on Windows** — `cv2.VideoCapture` was unreliable with ESP32 streams. A custom `MjpegStreamReader` that parses the multipart boundary works better.

---

## Valentine's Twist

The heart circuit — driven by an op-amp and wired to grow or shrink with detection — turns the installation into a Valentine's piece: the heart pulses when flowers are in view and settles when they’re gone. It’s a small analog detail that ties the whole experience together.

---

## Repo

[Make_Flora on GitHub](https://github.com/lee-cheng-han/Make_Flora)

---

*Built for Valentine's — flowers, music, and a heart that listens.*

# 02 — Flash the Grove Vision AI V2 via SenseCraft

Goal: a Grove Vision AI V2 running an object-detection model that can see your
target wildlife, with inference visible in the SenseCraft preview before we
involve the XIAO/MQTT plumbing.

## What you need

- Grove Vision AI V2 module
- OV5647 CSI camera connected to the Grove module's CSI flex connector
- USB-C cable directly from your laptop to the Grove module (do NOT connect
  the XIAO yet — only one device should talk to SenseCraft at a time)
- Chrome, Edge, or Opera (the SenseCraft Web Toolkit uses WebSerial, which
  Firefox/Safari do not support)

## 1. Connect to SenseCraft

Open <https://sensecraft.seeed.cc/ai/>, sign in (free account), then go to:

> SenseCraft AI Studio → **Vision AI V2** → click **Local Device**

It will prompt you to plug the device in and click Connect. Pick the serial
port that appears for the Grove module. If nothing appears:

- Hold the BOOT button on the Grove module while plugging in USB-C, then
  release. Try Connect again.
- On Windows you may need the CH343 UART driver.

Once connected, SenseCraft reads device info, current model info, and starts
a live preview.

## 2. Pick a starting model

For Phase 1 bring-up, deploy the simplest model that returns hits on your
target. SenseCraft has these directly deployable from the web UI:

| Model                    | Classes                          | Use for                               |
|--------------------------|----------------------------------|---------------------------------------|
| Person Detection         | person                           | Smoke test (point at yourself)        |
| Pet Detection            | cat, dog                         | Yard mammals: dog walkers, stray cats |
| COCO YOLOv8n             | 80 classes incl. bird, cat, dog  | First real wildlife use                |
| YOLO-World quick generate| any single class you type        | Fastest path to "bird"-only           |

**Recommended Phase 1 path**:

1. First flash **Person Detection** and verify you get bounding boxes around
   yourself in the SenseCraft preview. This proves the camera, the NPU, and
   the model deployment all work.
2. Then flash **YOLO-World quick-generate** with the class word `bird`.
   SenseCraft generates and quantizes a single-class model in ~1 minute and
   deploys it.
3. (Phase 3 only) Train a fine-grained species model off-device on a workstation
  or cloud GPU and upload it via SenseCraft's "Upload your own model" path.

To deploy any of the above: in SenseCraft, navigate to the model page and
click **Deploy Model** → select your connected Grove Vision AI V2 → wait for
flashing to complete (1–2 minutes).

## 3. Tune confidence and IoU

In the live preview, two sliders matter:

- **Confidence**: minimum probability to call something a detection. Start at
  **0.55**. Bump up if you get false positives on bark, leaves, etc. Lower if
  you're missing real birds.
- **IoU**: NMS overlap threshold. Default **0.45** is fine.

These settings are baked into the device — change them here, not later.

## 4. Verify the inference data structure

In the SenseCraft preview, click the **Output** or **Serial Monitor** tab.
You should see JSON-ish lines like:

```
{"type":1,"name":"INVOKE","code":0,"data":{"perf":[...],"boxes":[
  [142,88,168,152,87,14], ...
]}}
```

Each box is `[x, y, w, h, score, class_id]` (Seeed's SSCMA format). The XIAO
firmware in this package parses this exact structure via the
`Seeed_Arduino_SSCMA` library, so we don't need to write a parser.

## 5. **IMPORTANT**: turn off the SenseCraft live preview before continuing

The Grove Vision AI V2 cannot stream the live preview to SenseCraft and stream
inference results to the XIAO at the same time — they share the same I2C/UART
output. From the SenseCraft Process page, click **Stop**, then **Disconnect**.

If you skip this step, the XIAO firmware will see no data when you connect it
in the next step.

## 6. (Optional) Set up MQTT directly from SenseCraft Cloud

SenseCraft itself can publish detections to your MQTT broker — *if* you flash
a XIAO ESP32C3 with their `XIAO_C3_as_AT_module.bin` firmware and have it
provide WiFi to the Grove module via AT commands.

We're **not doing that** in this build, because you have a XIAO ESP32S3 Sense,
not a C3, and the S3 Sense is more useful as a programmable bridge with PIR
wake support coming in Phase 2. Skip the SenseCraft MQTT config UI entirely
and proceed to `03-xiao-firmware.md`.

Next step: `03-xiao-firmware.md`.

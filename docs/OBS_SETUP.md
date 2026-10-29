# Showing the verses in OBS Studio

Bible Presenter serves a clean presentation webpage on this computer. OBS Studio displays it with a **Browser Source**. The operator window is never captured, only the verses.

```
 Bible Presenter (operator window)  --->  local server 127.0.0.1:8765  --->  OBS Browser Source "Bible Output"
   search / preview / GO LIVE              /presentation (verses only)         livestream / projector
```

No internet connection is needed for this. The server only accepts connections from this computer.

## 1. Install OBS Studio

1. Download OBS Studio for Windows from the official site <https://obsproject.com/> (**Windows** button).
2. Run the installer with the default options. Start OBS. If the *Auto-Configuration Wizard* appears, you can choose *Optimize for streaming* or *Cancel* and configure later.

## 2. Start Bible Presenter and the server

1. Start Bible Presenter (`python main.py`, or `BiblePresenter.exe`).
2. At the bottom right, the OBS line should show a green dot: **● OBS · 127.0.0.1:8765/presentation**. If it is red or grey, open **Settings** → *OBS presentation server* and click **Start server**.
3. Click **Copy** on that line. The address is normally:

   ```
   http://127.0.0.1:8765/presentation
   ```

## 3. Create the scene and the Browser Source

1. In OBS, in the **Scenes** box (bottom left), click **+**, type `Bible Presentation`, click **OK**.
2. With that scene selected, in the **Sources** box click **+** → **Browser**.
3. Choose **Create new**, name it `Bible Output`, click **OK**.
4. In the properties window:
   * **URL:** paste `http://127.0.0.1:8765/presentation` (Ctrl+V).
   * Make sure **Local file** is **not** ticked.
   * **Width:** `1920`  **Height:** `1080`
   * Leave **Custom CSS** as it is, or empty it — the page does not need it.
   * Leave **Shutdown source when not visible** unticked (keeps the connection alive when you switch scenes).
   * Leave **Refresh browser when scene becomes active** unticked.
5. Click **OK**.

The source shows the dark navy background. That is correct while nothing is live.

## 4. Size and position

* If the canvas is 1920×1080 (OBS default: **Settings → Video → Base (Canvas) Resolution**), the source fills it exactly.
* To fit it to the canvas: right-click **Bible Output** → **Transform** → **Fit to screen** (Ctrl+F).
### Footer over the camera (the default)

Bible Presenter shows the verse in a **footer band** across the bottom of the screen; everything above the band is **transparent**. To put it on top of your camera:

1. Add your camera (*Sources → + → Video Capture Device*) to the **Bible Presentation** scene.
2. In the Sources list, make sure **Bible Output is above the camera** (drag it up). Sources higher in the list are drawn on top.
3. Keep `Bible Output` at the full canvas size (Ctrl+F). The band sits on the bottom edge by itself.
4. Adjust the band in Bible Presenter → *Layout*: **Footer height** (default 34 % of the screen) and **Footer background opacity** (default 85 %; lower = more camera visible behind the text, 0 % = text only). The band uses the *Background* colour, with a thin line in the *Reference* colour on top.
5. If long verses become small, raise *Footer height* or lower the font sizes slightly.

In the operator preview, the black area above the band is where your camera will show.

In footer mode, **Hide** (Ctrl+B) hides the band only, so the camera stays visible (it does not black out your stream).

### Full screen (projector, or verses only)

In **Settings**, set *Layout → Display* to **Full screen**. The verses then fill the whole 16:9 slide on the *Background* colour. Here you can also tick **Transparent background** (in *Show / hide*) for a text-only overlay; in this mode *Black screen* shows black.

The page always keeps a 16:9 design and scales itself, so any Browser Source size works (for example 1280×720 or a smaller box).

## 5. Test it

1. In Bible Presenter type `John 3:16-18`, press **Enter**, click **GO LIVE** → John 3:16 appears in the footer in OBS, in English and French, with `(1/3)` after the reference.
2. Click **GO LIVE** again (the next verse is queued automatically), or **Next ▶** on the Live card (Ctrl+Right) → 3:17, then 3:18.
3. Type `Psalm 23`, press **Enter** → the *preview* changes, **OBS stays on John 3**. Click **GO LIVE** → OBS shows Psalm 23:1.
4. In **Settings** → *Layout*, switch **Bilingual layout** between *Side by side* and *Stacked*, and **Order** between *English first* / *French first* → OBS updates immediately.
5. Click **Hide** (Ctrl+B) → the footer disappears (camera still visible). Click **Show** → the verse comes back.
6. Use **Next ▶** (Ctrl+Right) → OBS moves to the next verse.

## 6. Save the OBS setup

OBS saves scenes automatically when you close it. To keep a backup: **Scene Collection → Export**, save the `.json` file somewhere safe. (Import it later with *Scene Collection → Import*.)

## Recovery: OBS shows nothing or an old verse

The page reconnects by itself within a few seconds when the server comes back (for example after restarting Bible Presenter). If it does not:

1. In Bible Presenter check the server status is **● Running** and the port matches the OBS URL.
2. Click **Reconnect output (reload OBS page)** in Settings → *OBS presentation server*.
3. Still nothing? In OBS, double-click **Bible Output** and click **Refresh cache of current page** (or right-click the source → *Properties* → *Refresh*).
4. Check the URL in OBS is exactly `http://127.0.0.1:PORT/presentation` (with your port).
5. As a test, click **Open in browser** in Bible Presenter. If the browser shows the verse but OBS does not, recreate the Browser Source.

Tip: to see a small connection dot for troubleshooting, use `http://127.0.0.1:8765/presentation?debug=1` (green = connected, red = reconnecting). Do not use `?debug=1` during a live service.

## Projector without OBS

In **Settings** → *Fullscreen output*, pick the projector's screen and click **Open fullscreen**. It shows the same live slide as OBS. Press **Esc** on that screen (or double-click it, or click **Close**) to close it.

# Manual OBS test checklist

Do this once after installing (and after each new build) on the actual church computer, before a service.
Tick each box. Write down anything that fails.

**Setup**

- [ ] Bible Presenter starts; no error message.
- [ ] The top bar shows **KJV** and **LSG** (KJV button → *Bible library…* is green: complete English and French Bibles).
- [ ] Bottom right: **● OBS · 127.0.0.1:8765/presentation** with a green dot.
- [ ] OBS: scene **Bible Presentation** with Browser Source **Bible Output**, 1920×1080, that URL.

**Preview / live**

- [ ] Type `John 3:16` in the search bar → Enter. KJV and LSG appear side by side in Garamond; the **Next** preview shows the slide.
- [ ] OBS has **not** changed.
- [ ] Click **GO LIVE** → OBS shows John 3:16 in English and French in a **footer band** at the bottom, reference below the text, nothing else (no buttons, menus, scrollbars). The camera is visible above the band.
- [ ] Type `Jean 3:16-18` → preview changes; OBS still shows 3:16 only.
- [ ] **GO LIVE** → OBS shows Jean 3:16 with `(1/3)`; the **Next** preview now shows 3:17 ("verse 2 of 3"). GO LIVE again → 3:17, then 3:18.
- [ ] Click verse 18 in the table → it is highlighted and becomes **Next**.
- [ ] The **Live** card shows the same verse as OBS.
- [ ] **Browse**: click *Psalms → 23 → verse 1*, then Shift+click verse 6 → the passage shows Psalm 23:1–6; Next shows verse 1 of 6.
- [ ] Search bar: `berger` → matching verses; click one → it opens.
- [ ] **☆ Save** → becomes **★ Saved** and appears as a ★ chip at the bottom; clicking a chip opens that passage.
- [ ] Recent chips list the passages you viewed.
- [ ] Type `John 30:1` → red message *John has 21 chapters; chapter 30 does not exist.*

**Live controls**

- [ ] **Next ▶** / Ctrl+Right → OBS moves one verse forward (crosses into the next chapter at the end).
- [ ] **◀ Prev** / Ctrl+Left → back.
- [ ] **Hide** / Ctrl+B → the footer disappears in OBS (camera still visible); the Live card shows *HIDDEN* and the button says **Show**. **Show** → the same verse comes back.
- [ ] Settings → **Clear output** → OBS shows no verse; **Restore last slide** (Ctrl+R) brings it back.

**Layout and appearance** (in **Settings**; each change should appear in OBS within a second)

- [ ] Layout *Stacked*: English on top, French below with a divider.
- [ ] Order *French first* (both layouts).
- [ ] Uncheck *Show English text* → French only, full width. Re-check it.
- [ ] *Show language labels* on/off. *Show Bible reference* on/off. Reference position *Top*.
- [ ] Change background, text and reference colours, font, sizes, line spacing, alignment.
- [ ] GO LIVE on `Romans 8:28-39` → `(1/12)` shown; Next live verse steps through all 12 verses.
- [ ] Footer height 25 % and 45 %, footer opacity 0 % and 100 % → band changes in OBS; text never cut off. Set them back.
- [ ] Longest verse `Esther 8:9` in the footer → all text visible (smaller font).
- [ ] *Display: Full screen* → verses fill the screen. *Verses per slide: Whole selection* + `Genesis 1` → split into pages, no text cut off. *Black screen* → black. Then set *Display: Footer* and *One verse at a time* again.
- [ ] In full screen, *Transparent background* on → camera shows through. Turn it off again.
- [ ] Close and reopen Bible Presenter → all appearance settings and the window position are remembered.

**Different sizes**

- [ ] Resize the Browser Source in OBS to a small box (e.g. 960×540) → text scales down, nothing cut off.
- [ ] Set the Browser Source width/height to 1280×720 → still correct.

**Reliability**

- [ ] Click **Stop server** → OBS keeps the last image. Click **Start server** → within a few seconds OBS is live again (no refresh needed).
- [ ] Close Bible Presenter completely and restart it → OBS reconnects by itself.
- [ ] **Reconnect output (reload OBS page)** → OBS page reloads and shows the current state.
- [ ] Disconnect the internet (Wi-Fi off) → everything above still works.
- [ ] Settings → *Fullscreen output* → **Open fullscreen** on the projector screen; Esc closes it.
- [ ] Save the OBS scene collection (Scene Collection → Export).

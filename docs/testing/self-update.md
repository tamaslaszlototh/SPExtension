# Testing self-update (Shelf+ v0.9.2)

From this version on, **Shelf+ updates itself** from GitHub:

- When Painter starts (at most once a day), Shelf+ asks GitHub for a newer version. If there is one, a small window shows what is new, with **Update**, **Later** and **Skip this version**.
- **☰ → Check for updates** asks at any time.
- **Update** downloads the new version in the background. It becomes active **the next time Painter starts**; nothing changes in the running Painter.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights

One run takes about 10 minutes. Write the results in the [table at the end](#results).

**Before you start:** the developer tells you when **v0.9.3** has been published. Install v0.9.2 by hand first (step 1); v0.9.3 is the update Shelf+ should offer.

v0.9.0 and v0.9.1 cannot update themselves (their *Check for updates* ends with "HTTP 302"), so replace them by hand with v0.9.2.

## 1. Install v0.9.2 by hand

1. Close Painter.
2. Download **ShelfPlus-v0.9.2.zip** from the [v0.9.2 release page](https://github.com/tamaslaszlototh/ShelfPlus/releases/tag/v0.9.2).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Open `%APPDATA%\ShelfPlus` (paste it into the Explorer address bar). If there is a `panel.json`, open it in Notepad. In the `"updater"` part, set `"lastCheck": null` and `"skippedVersion": null`, and save. This makes Shelf+ check for updates on the next start instead of waiting a day. Leave `layout.json` (your Buttons) alone.
6. If `%APPDATA%\ShelfPlus\versions` holds a `0.9.3` folder, delete it.

## 2. The checks

### A. Painter offers the update on start

1. Start Painter.
   - ✅ Within a few seconds a window **Shelf+ update** opens: *"Shelf+ v0.9.3 is available (you have v0.9.2)."*, with the release notes below.
   - ✅ Painter stays usable while the window is open (you can click in the layer stack).
2. Click **☰** on the Panel. ✅ The first line says **Shelf+ v0.9.2**.
3. Note what your Panel looks like (Groups, Buttons, tile size).
4. In the update window, click **Update**.
   - ✅ The Panel's top bar says *"Downloading Shelf+ v0.9.3…"* for a moment.
   - ✅ A message says *"Update downloaded; it will be active the next time Painter starts."*
   - ✅ `%APPDATA%\ShelfPlus\versions` now has a `0.9.3` folder, and no folder starting with `.`.
5. Restart Painter.
   - ✅ No update window opens.
   - ✅ **☰** shows **Shelf+ v0.9.3**.
   - ✅ Your Panel looks exactly as in step 3, and your Buttons work.

### B. Skip this version

1. Close Painter. Delete `%APPDATA%\ShelfPlus\versions\0.9.3`. In `panel.json`, set `"lastCheck": null` again and save.
2. Start Painter. ✅ **☰** shows **Shelf+ v0.9.2**, and the update window offers v0.9.3.
3. Click **Skip this version**. ✅ The window closes and nothing is downloaded (no `0.9.3` folder).
4. Close Painter. In `panel.json`, ✅ `"skippedVersion"` is now `"0.9.3"`. Set `"lastCheck": null` once more, keep the skipped version, and save.
5. Start Painter. ✅ No update window opens.
6. **☰ → Check for updates.** ✅ The window offers v0.9.3 again (a check you ask for yourself ignores the skip). Click **Update** and restart Painter to end on v0.9.3.

### C. Check for updates without a network

1. Turn the network off (Wi-Fi off, or unplug the cable).
2. **☰ → Check for updates.**
   - ✅ A message says *"Could not check for updates: …"* with a reason.
   - ✅ Painter and the Panel keep working.
3. Turn the network back on. **☰ → Check for updates.** ✅ *"Shelf+ v0.9.3 is up to date."*

If anything fails, click **☰ → Copy diagnostics** and paste the result into a message.

## Results

| Check | Home (11.1) | Work (12.2) | Notes |
|---|---|---|---|
| A. Offered on start, Update, restart shows v0.9.3, Layout untouched | | | |
| B. Skip: no window on restart; manual check offers it again | | | |
| C. No network: error message; back online: up to date | | | |

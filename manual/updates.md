# Updates & diagnostics

## Updates

Shelf+ updates itself from GitHub.

- When Painter starts, Shelf+ checks for a newer release, at most once a day.
- **☰ → Check for updates** checks at any time.

When a newer version is available, a **Shelf+ update** window shows what is new. Painter
stays usable while it is open.

| Choice | What happens |
|---|---|
| **Update** | The new version downloads in the background. It becomes active **the next time Painter starts**. Nothing changes in the running Painter |
| **Later** | Nothing now. Shelf+ asks again on a later start |
| **Skip this version** | Shelf+ does not offer this version on start again. **Check for updates** still offers it |

Your Buttons, Groups and settings stay as they are after an update.

!!! note "A manual reinstall"
    Rarely, a release needs a newer version of the part you installed by hand. The update
    window then says *This version needs a manual reinstall*. Download the zip from the
    [Releases page](https://github.com/tamaslaszlototh/ShelfPlus/releases) and
    [install it](getting-started.md#install) as the first time.

!!! tip "If a new version fails to start"
    Shelf+ goes back to the previous version by itself, and Painter shows *Shelf+ vX.Y.Z
    failed to start; reverted to …*. Please [report it](#report-a-problem).

## Copy diagnostics

**☰ → Copy diagnostics** copies the Shelf+, loader, Painter, Python and Qt versions and
the last 200 lines of the log to the clipboard. Paste it into a bug report.

!!! tip
    Copy diagnostics right after the problem, **before** restarting Painter. That way the
    log still holds what happened.

The full log is in `%APPDATA%\ShelfPlus\logs\`.

## Report a problem

1. Click **☰ → Copy diagnostics**.
2. Open a new issue on [GitHub](https://github.com/tamaslaszlototh/ShelfPlus/issues).
3. Describe what you did, what you expected, and what happened.
4. Paste the diagnostics.

# Pen hover and tooltips in Painter (Windows, Qt tablet input)

Research for [#19](https://github.com/tamaslaszlototh/SPExtension/issues/19).
Context: in the [#8](https://github.com/tamaslaszlototh/SPExtension/issues/8) prototype,
the Button's hover name (a `QToolTip` set with `setToolTip`) appears with the mouse
but not with the pen. The decided fallback is a toggleable caption under the tile.

## Short answer

- **In plain Qt 6 on Windows, pen hover tooltips should work.** A hovering pen produces
  `TabletMove` events. Plain widgets ignore those by default, so Qt turns each one into a
  synthesized `MouseMove`. That `MouseMove` arms the normal tooltip timer. The Qt bug
  where widget tooltips were missing with a tablet (QTBUG-57485) was fixed in Qt 5.12.
- **So something in Painter's process probably breaks that chain.** Either Painter turned
  off `AA_SynthesizeMouseForUnhandledTabletEvents`, or Painter's app-level or
  ancestor-widget code accepts the tablet events. In both cases no synthesized mouse move
  reaches the widget, so it also gets no `Enter`/`Leave`/`HoverMove` from the pen. This is
  an inference: Painter's source is closed, and the probe script below measures it.
- **It can be solved in our code, without Painter's help.** We do not need the built-in
  tooltip. We show our own with `QToolTip.showText()`, triggered by one of three
  mechanisms that do not depend on mouse synthesis (B, C and D below). The most robust is
  D: while the Panel is visible, poll the cursor position (`QCursor.pos()` plus
  `QApplication.widgetAt()` on a ~100 ms timer). The Windows cursor follows the hovering
  pen, so this needs no events at all.
- **The tablet driver's Windows Ink setting is not a usable lever.** Painter needs Windows
  Ink for pen pressure. With Ink off, the pen would move the cursor as a normal mouse and
  tooltips would likely work, but pressure would be lost. It is only useful as a
  diagnostic.

## How it works in Qt 6 (Windows, Windows Ink / WM_POINTER)

All source references are qtbase `6.5` (the line Painter's PySide6 is most likely built on;
the probe records the exact `qVersion()`).

1. **The platform plugin turns pen messages into tablet events, not mouse events.**
   `qwindowspointerhandler.cpp`, `translatePenEvent`:
   - `WM_POINTERENTER` sends a tablet *proximity* event and sets `m_needsEnterOnPointerUpdate`.
     The window-level `Enter` is sent on the next `WM_POINTERUPDATE` (`handleEnterEvent`).
   - `WM_POINTERUPDATE` sends `handleTabletEvent` both in contact and in hover;
     `IS_POINTER_INCONTACT_WPARAM` only decides the button state.
   - The mouse messages that Windows synthesizes from the pen (`MI_WP_SIGNATURE` in
     `GetMessageExtraInfo`) are **dropped** in `translateMouseEvent` ("ignoring synth-mouse
     event for tablet event from …"). The driver's "Let me use my pen as a mouse" option
     therefore does not reach Qt widgets as mouse input.
   - `qwindowsintegration.cpp`: the integration calls `setPlatformSynthesizesMouse(false)`,
     so Qt itself must synthesize the mouse events. The `nowmpointer` platform option falls
     back to the legacy (WinTab) tablet path; Painter uses Windows Ink since 2019.3 (Adobe doc).
   Source: https://code.qt.io/cgit/qt/qtbase.git/tree/src/plugins/platforms/windows/qwindowspointerhandler.cpp?h=6.5 ,
   https://code.qt.io/cgit/qt/qtbase.git/tree/src/plugins/platforms/windows/qwindowsintegration.cpp?h=6.5

2. **The tablet event goes to the widget under the pen.** `qwidgetwindow.cpp`,
   `handleTabletEvent`: `childAt(pos)`, a fresh `QTabletEvent` with `setAccepted(false)`,
   `forwardEvent`, then the accepted flag is copied back to the original event.
   This path does **not** dispatch `Enter`/`Leave` to child widgets. Widget-level
   enter/leave and hover come only from mouse events.
   Source: https://code.qt.io/cgit/qt/qtbase.git/tree/src/widgets/kernel/qwidgetwindow.cpp?h=6.5

3. **Delivery and propagation.** `QApplication::notify` walks a tablet event up the parent
   chain until a widget accepts it. It stops at the top-level window or at
   `WA_NoMousePropagation`. App-level and object-level event filters run inside
   `notify_helper` for each widget. Filters installed later run first ("the filter that was
   installed last is activated first", `QObject::installEventFilter` docs).
   Source: https://code.qt.io/cgit/qt/qtbase.git/tree/src/widgets/kernel/qapplication.cpp?h=6.5 ,
   https://doc.qt.io/qt-6/qobject.html#installEventFilter

4. **A plain widget ignores a hover TabletMove.** QWidget docs: "If tablet tracking is
   switched off, tablet move events only occur if the stylus is in contact with the tablet,
   or at least one stylus button is pressed". With tablet tracking on, they occur during
   hover too. "The default implementation ignores the event."
   Source: https://doc.qt.io/qt-6/qwidget.html#tabletEvent , https://doc.qt.io/qt-6/qwidget.html#tabletTracking-prop

5. **An unaccepted tablet event becomes a mouse event.** `qguiapplication.cpp`,
   `processTabletEvent`: if `!tabletEvent.isAccepted() && !platformSynthesizesMouse &&
   qApp->testAttribute(Qt::AA_SynthesizeMouseForUnhandledTabletEvents)`, a
   `TabletMove` becomes a `MouseMove`, marked `Synthetic`, and goes to `processMouseEvent`.
   Qt docs: `AA_SynthesizeMouseForUnhandledTabletEvents` ("All tablet events that are not
   accepted by the application will be translated to mouse events instead") is "enabled by
   default", since 5.7. `QTabletEvent` docs: "Qt will first send a tablet event, then if it
   is not accepted by any widget, it will send a mouse event."
   Source: https://code.qt.io/cgit/qt/qtbase.git/tree/src/gui/kernel/qguiapplication.cpp?h=6.5 ,
   https://doc.qt.io/qt-6/qt.html#ApplicationAttribute-enum , https://doc.qt.io/qt-6/qtabletevent.html

6. **The tooltip comes from that MouseMove.** `QApplication::notify`: a spontaneous
   `MouseMove` with `buttons() == 0` inside the widget's rectangle sets `toolTipWidget` and
   starts `toolTipWakeUp`. When the timer fires (`QApplication::event`, `Timer`), it sends
   `QEvent::ToolTip` if the window is active or `WA_AlwaysShowToolTips` is set.
   There is no `ToolTip` path from tablet events.
   Source: https://code.qt.io/cgit/qt/qtbase.git/tree/src/widgets/kernel/qapplication.cpp?h=6.5

7. **History.** QTBUG-57485 ("Tooltips not shown when using a graphic tablet instead of
   mouse", Linux, 5.7) was fixed in 5.12. The fix delivers tablet hover events and falls back
   to synthesized mouse when they are not accepted. A maintainer confirmed tooltips and
   hover highlights with a stylus on 5.12.
   Source: https://bugreports.qt.io/browse/QTBUG-57485 (REST: `qt-project.atlassian.net/rest/api/2/issue/QTBUG-57485`)
   QTBUG-114665 shows apps disabling `AA_SynthesizeMouseForUnhandledTabletEvents` on Qt 6.5
   as a workaround for pen problems. A large app (Painter) doing the same is plausible.
   Source: https://bugreports.qt.io/browse/QTBUG-114665

**So a missing pen tooltip means one of these links is broken:** (5) attribute off, or
(3)/(5) the tablet event is accepted (by a Painter app-level filter that calls `accept()`, or
by an ancestor widget). Less likely: (1) the pointer message never arrives (VM, driver).
That would also break pen painting, so it is ruled out in practice.

## Painter-side facts (Adobe)

- Painter has used Windows Ink since 2019.3, and WinTab before that. "Windows Ink has to be
  enabled in the driver settings of the Graphic Tablet." Recommended: "Let me use my pen as a
  mouse in some desktop apps" = Enabled ("If disabled, this setting can lead to some
  interaction issues with UI parameters"). The page says nothing about hover or tooltips.
  Source: https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/technical-support/configuring-pens-and-tablets
- An Adobe staffer says Windows Ink is required for pen pressure in Painter. Users report pen
  overlay/modifier oddities that go away with Ink off, but so does pressure. These are
  community sources, lower trust.
  Source: https://community.adobe.com/questions-59/substance-pinter-mmb-and-windows-ink-626825 ,
  https://community.adobe.com/questions-59/the-alt-and-ctrl-displays-that-appear-under-the-cursor-when-using-the-pen-tab-do-not-disappear-i-627400
- I found no Painter documentation or forum report on pen hover tooltips in plugin widgets.
- No public Painter preference selects the tablet API.

## Answers to the ticket's questions

| Question | Answer |
|---|---|
| Does the widget get `Enter`/`HoverMove`/`MouseMove` on pen hover? | Only through Qt's mouse synthesis. Windows' own pen-to-mouse messages are dropped by Qt. If synthesis is blocked in Painter, the widget gets none of them. This is the likely current state; the probe verifies it. |
| `TabletEnterProximity` / `TabletMove`? | Proximity goes **only to `QApplication`** (Qt docs), so only an app-level filter sees it. `TabletMove` in hover reaches a widget only with `setTabletTracking(True)`, and only if no earlier filter consumes it. |
| Does Painter swallow it? | Unknown, because Painter is closed source. The probe tells us: if the app-level filter (`app`) sees `TabletMove` on our button but the widget (`obj`/`hndl`) does not, a Painter filter consumes it. If both see it but no `MouseMove` follows, synthesis is off or the event is accepted. |
| Own tooltip with `QToolTip.showText`? | Yes. `showText(globalPos, text, widget)` works from any trigger; it does not need a `ToolTip` event. Leaving must be detected by us (cursor polling), because `Leave` may not come with the pen. |
| Does Windows Ink on/off matter? | It changes the input path: Ink off means the driver moves a plain mouse, so tooltips likely work but pressure is gone. Not a solution, only a diagnostic. The driver's "use pen as mouse" option does not affect Qt widgets (Qt drops those messages). |

## Recommended solution (for the spec)

1. Keep `setToolTip(name)` on each Button: it covers the mouse, and the accessible name.
2. Add one **pen hover helper** for the whole Panel. It shows `QToolTip.showText` after a
   dwell (~600 ms) and hides it when the cursor leaves the Button's rect (100 ms
   `QCursor.pos()` check). Trigger, in order of preference, picked by the probe result:
   - **D, cursor polling (default candidate):** a ~100 ms `QTimer`, running only while the
     Panel is visible, calls `QApplication.widgetAt(QCursor.pos())`. It needs no events, so
     it survives whatever Painter does with tablet events. Cost: one cheap call per tick; it
     can sleep when the cursor is outside the Panel's global rect. To avoid a double tooltip
     with the mouse, the helper does nothing if a Qt tooltip is already visible
     (`QToolTip.isVisible()`). Alternatively it runs only after a `TabletEnterProximity`
     seen by an app filter, until `TabletLeaveProximity`.
   - **B, `setTabletTracking(True)` + `tabletEvent`** on the Buttons (call `ev.ignore()`).
     This is the cleanest, if the probe shows that the `hndl` layer receives events.
   - **C, app-level event filter** on `QApplication`, installed last so it runs first. It
     catches `TabletMove` before Painter's filters, but a Python filter on every app event
     costs performance. Use it only if B fails and D is unsuitable.
3. The toggleable caption under the tile (decided in #8) stays as the last fallback.
4. Hover highlight (`:hover` style) has the same root cause. With the pen, it may be missing
   too. The helper can set a dynamic property (e.g. `penHover=true`) for the style sheet if
   needed.

## Measurement for the friend (HITL)

Script: [`research/pen_hover_probe/spx_pen_probe.py`](pen_hover_probe/spx_pen_probe.py), a
throwaway Painter plugin. **Not run here (no Painter or PySide6 on the dev machine); only
syntax-checked.**

1. Copy it to `Documents\Adobe\Adobe Substance 3D Painter\python\plugins\`, and enable it in
   Painter's Python menu (`spx_pen_probe`). The "SPX pen probe" dock appears.
2. Reset, then **with the mouse** rest ~3 s on buttons A, B, C and D. Note which ones show a
   tooltip.
3. Reset, then **with the pen hovering** (not touching) do the same on A, B, C and D.
4. With the pen, hover over one of **Painter's own** toolbar icons. Does Painter's tooltip
   appear? If it does not, the whole app is affected, not just us.
5. Type the observations into the text box, press **Save report**, and send the
   `%APPDATA%\SPExtension\pen_probe_*.txt` file.
6. Optional: repeat step 3 with Windows Ink off in the driver (restart Painter), then turn
   it back on.
7. Do it on both machines (11.1.0 home, 12.2.0 work). The work machine does not need admin
   rights for this.

What the report tells us:
- `AA_SynthesizeMouseForUnhandledTabletEvents=False`: Painter turned off synthesis
  (cause 5).
- `app … TabletMove` present for A, but no `obj A MouseMove`: the event is accepted
  somewhere (cause 3), or synthesis is off.
- `hndl B TabletMove` present: variant B is usable.
- "D: custom tooltip shown" in the notes: variant D works (expected regardless).
- `Qt runtime` and `Painter` versions, for the record (11.1 vs 12.2).

## Open risks

- Painter's internal tablet handling is closed source; the cause is inferred until the probe
  runs.
- `QApplication.widgetAt` returns the topmost widget. Over a floating Panel or popup it
  behaves as expected, but it must be mapped to the Button (the child label/icon may be
  returned, so walk up parents).
- `QToolTip.showText` from our code while Painter's own (QML) tooltips are up: possible
  overlap; low impact.
- `QCursor.pos()` follows the pen only while the OS cursor follows it (Windows Ink default).
  In "pen as mouse disabled" setups that should still hold, because Windows moves the cursor
  for pen pointers, but this is unverified.

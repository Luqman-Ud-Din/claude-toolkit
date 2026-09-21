# WCAG 2.2 Level A + AA checklist

Every Level A and AA success criterion in WCAG 2.2, with what to check and how.
Group findings under these ids (`WCAG-1.1.1` etc.). Criteria marked **new** were
added in 2.2; 4.1.1 Parsing was removed in 2.2 and must not be cited.
"Auto" = axe-core / template_scan.py can detect it; "Manual" = needs a person.

## Principle 1 - Perceivable

| Id | Name (level) | What to check | How |
|---|---|---|---|
| 1.1.1 | Non-text Content (A) | Every `<img>`, icon button, chart, CAPTCHA has a text alternative; decorative images have `alt=""` | Auto (`image-alt`, `svg-img-alt`, `button-name`); manual for charts (data table or summary) |
| 1.2.1 | Audio-only / Video-only (A) | Transcript for audio, description for video-only | Manual, only if media exists |
| 1.2.2 | Captions (Prerecorded) (A) | Captions on prerecorded video with audio | Manual |
| 1.2.3 | Audio Description or Media Alternative (A) | Description track or transcript | Manual |
| 1.2.4 | Captions (Live) (AA) | Live video has captions | Manual |
| 1.2.5 | Audio Description (Prerecorded) (AA) | Audio description track | Manual |
| 1.3.1 | Info and Relationships (A) | Labels programmatically tied to inputs, headings are real `<h*>`, tables have `<th scope>`, lists are `<ul>/<ol>`, groups use `<fieldset>/<legend>` | Auto (`label`, `th-has-data-cells`, `list`, `definition-list`); template_scan `input-no-label` |
| 1.3.2 | Meaningful Sequence (A) | DOM order matches visual order (no CSS `order`/`flex-direction: row-reverse` that changes reading order) | Manual: tab through, compare with layout |
| 1.3.3 | Sensory Characteristics (A) | Instructions do not rely on shape/position/sound only ("click the green button on the right") | Manual: grep help text |
| 1.3.4 | Orientation (AA) | Works in portrait and landscape; no `orientation` lock (Capacitor `screenOrientation`) | Manual / config |
| 1.3.5 | Identify Input Purpose (AA) | `autocomplete` on name/email/phone/address/card fields | Auto (`autocomplete-valid`); grep forms for missing `autocomplete` |
| 1.4.1 | Use of Color (A) | Status/errors/links distinguishable without colour (icon, text, underline) | Manual on the densest page |
| 1.4.2 | Audio Control (A) | Auto-playing audio >3 s can be paused | Manual, if any |
| 1.4.3 | Contrast (Minimum) (AA) | Text 4.5:1 (3:1 for large text) in every theme | Auto (`color-contrast`) per theme; DevTools CSS Overview |
| 1.4.4 | Resize Text (AA) | Usable at 200% browser zoom without loss | Manual: zoom 200% on key pages |
| 1.4.5 | Images of Text (AA) | No text baked into images (logos excepted) | Manual |
| 1.4.10 | Reflow (AA) | No horizontal scroll at 320 px width (except tables/maps) | Manual: DevTools 320 px |
| 1.4.11 | Non-text Contrast (AA) | UI component borders, focus rings, icons 3:1 | Manual + DevTools picker |
| 1.4.12 | Text Spacing (AA) | Still readable with line-height 1.5, paragraph 2x, letter 0.12em, word 0.16em | Manual: bookmarklet / user stylesheet |
| 1.4.13 | Content on Hover or Focus (AA) | Tooltips/popovers dismissible (Esc), hoverable, persistent | Manual on tooltips/menus |

## Principle 2 - Operable

| Id | Name (level) | What to check | How |
|---|---|---|---|
| 2.1.1 | Keyboard (A) | Every action reachable by keyboard; no click-only `<div>`s; drag-and-drop has a keyboard path | template_scan `click-on-non-interactive`; manual tab-through |
| 2.1.2 | No Keyboard Trap (A) | Focus can leave every widget (editors, maps, embedded iframes); modals trap *intentionally* and release on close | Manual; template_scan `dialog-no-focus-trap` flags the inverse (focus escaping a modal) |
| 2.1.4 | Character Key Shortcuts (A) | Single-key shortcuts can be turned off/remapped or only active on focus | grep `keydown` handlers on `document` for single letters |
| 2.2.1 | Timing Adjustable (A) | Session timeouts warn and can be extended; auto-logout has a 20 s+ warning | Manual: token expiry flow |
| 2.2.2 | Pause, Stop, Hide (A) | Carousels, tickers, auto-refresh can be paused | grep `setInterval` UI refreshers |
| 2.3.1 | Three Flashes (A) | Nothing flashes >3 times/second | Manual |
| 2.4.1 | Bypass Blocks (A) | Skip link to `<main>`, landmarks (`<main>`, `<nav>`, `<header>`) | Auto (`bypass`, `landmark-one-main`, `region`) |
| 2.4.2 | Page Titled (A) | `<title>` changes per route and describes the page | Auto (`document-title`) per route; grep for `TitleStrategy`/`useHead`/`document.title` |
| 2.4.3 | Focus Order (A) | Tab order follows meaning; modals move focus in and restore it; no positive `tabindex` | Auto (`tabindex`); template_scan `dialog-no-focus-trap`, `positive-tabindex`; manual |
| 2.4.4 | Link Purpose (In Context) (A) | No bare "click here"/"more"; icon links named | Auto (`link-name`); manual |
| 2.4.5 | Multiple Ways (AA) | Two ways to reach pages (nav + search/sitemap) unless process step | Manual |
| 2.4.6 | Headings and Labels (AA) | Headings/labels describe content; one `<h1>`; no skipped levels | Auto (`heading-order`, `page-has-heading-one`, `empty-heading`) |
| 2.4.7 | Focus Visible (AA) | Focus indicator visible on every focusable element; no `outline: none` without replacement | template_scan `outline-none`; manual tab-through |
| 2.4.11 | Focus Not Obscured (Minimum) (AA) **new** | Focused element not fully hidden behind sticky headers/footers/cookie banners | Manual: tab to items under sticky bars |
| 2.5.1 | Pointer Gestures (A) | Multi-point/path gestures (pinch, swipe) have single-pointer alternative | Manual on maps/carousels/swipe-to-delete |
| 2.5.2 | Pointer Cancellation (A) | Actions on `mouseup`/`click`, not `mousedown`; drag can be aborted | grep `mousedown`/`pointerdown` handlers that commit |
| 2.5.3 | Label in Name (A) | Accessible name contains the visible label text (`aria-label` must not contradict visible text) | Auto (`label-content-name-mismatch`); grep `aria-label` on elements with text |
| 2.5.4 | Motion Actuation (A) | Shake/tilt features have UI alternative and can be disabled | Manual, if any |
| 2.5.7 | Dragging Movements (AA) **new** | Drag-and-drop (reorder, sliders, kanban) has a non-drag alternative (buttons, keyboard) | grep `cdkDrag`, `draggable`, `react-beautiful-dnd`, `Sortable`; manual |
| 2.5.8 | Target Size (Minimum) (AA) **new** | Interactive targets at least 24x24 CSS px or spaced apart (icon buttons, table row actions, close X) | Auto (`target-size`); manual on dense grids |

## Principle 3 - Understandable

| Id | Name (level) | What to check | How |
|---|---|---|---|
| 3.1.1 | Language of Page (A) | `<html lang>` set and updated on locale switch | Auto (`html-has-lang`, `html-lang-valid`); template_scan `html-no-lang` |
| 3.1.2 | Language of Parts (AA) | Inline foreign text has `lang` (e.g. Arabic product names in an English UI) | Manual |
| 3.2.1 | On Focus (A) | Focusing does not trigger navigation/submit | Manual |
| 3.2.2 | On Input (A) | Changing a select/checkbox does not auto-submit or navigate without warning | grep `(change)="submit`/`onChange={...navigate` |
| 3.2.3 | Consistent Navigation (AA) | Nav in the same order on every page | Manual |
| 3.2.4 | Consistent Identification (AA) | Same icon/label for the same function everywhere | Manual |
| 3.2.6 | Consistent Help (A) **new** | Help/contact link in the same place on every page that has it | Manual |
| 3.3.1 | Error Identification (A) | Errors described in text, tied to the field (`aria-describedby`), announced (`role="alert"`/`aria-live`) | grep error templates for `role="alert"`; manual |
| 3.3.2 | Labels or Instructions (A) | Visible labels or instructions for inputs; required marked; format hints | template_scan `input-no-label`, `placeholder-only-label` |
| 3.3.3 | Error Suggestion (AA) | Error text says how to fix ("Enter a date as DD/MM/YYYY") | Manual: read validation messages |
| 3.3.4 | Error Prevention (Legal, Financial, Data) (AA) | Orders/payments/deletions are reversible, confirmed, or reviewable before commit | Manual on checkout, delete flows |
| 3.3.7 | Redundant Entry (A) **new** | Information entered earlier in the same process is auto-filled or selectable (shipping = billing) | Manual on multi-step forms |
| 3.3.8 | Accessible Authentication (Minimum) (AA) **new** | Login has no cognitive test (no memorized puzzle/CAPTCHA without alternative); password managers/paste allowed (`onpaste="return false"` forbidden) | grep `onpaste`, `autocomplete="off"` on password; manual |

## Principle 4 - Robust

| Id | Name (level) | What to check | How |
|---|---|---|---|
| 4.1.2 | Name, Role, Value (A) | Custom controls expose name/role/state via ARIA; icon buttons named; `aria-*` valid and on allowed roles; `aria-expanded`/`aria-selected` updated | Auto (`button-name`, `aria-*` rules); template_scan `icon-button-no-name`, `dialog-no-name` |
| 4.1.3 | Status Messages (AA) | Toasts, "3 results found", "Saved", loading states announced via `role="status"`/`aria-live` without moving focus | grep toast/snackbar component for `aria-live`/`role="status"`; manual |

## Severity guidance

- Failure that blocks a required flow (checkout, login, order entry) for keyboard or
  screen-reader users with no alternative: **High** (Critical if the flow is legally mandated
  or there is no other way to pay/contact).
- Same failure on secondary pages, or contrast/label gaps that slow but do not block: **Medium**.
- New 2.2 criteria (2.4.11, 2.5.7, 2.5.8, 3.2.6, 3.3.7, 3.3.8): rate on impact like the others;
  do not discount because they are new.
- Hardening (missing `autocomplete`, `lang` on a part): **Low**.

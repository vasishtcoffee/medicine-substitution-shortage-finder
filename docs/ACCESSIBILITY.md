# Accessibility implementation and evidence

Target: WCAG 2.2 AA. **No full conformance claim.** Criteria references: [WCAG 2.2](https://www.w3.org/TR/WCAG22/), [reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html), [focus visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html), [target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).

## Criteria checklist

| Criterion | Implemented | Tested | Remaining/unverified |
|---|---|---|---|
| 1.3.1 Information/relationships | Landmarks, h1/h2, labeled dashboard articles, list statuses, table header scopes | Source; patient DOM snapshots | Every screen/assistive technology |
| 1.4.1 Use of color | Text and symbols accompany statuses; bold/border active nav | Source; patient browser views | All states |
| 1.4.3 Contrast | Actual text token pairs meet 4.5:1 in calculation | 35-pair script includes text/control/focus cases; table below | Every rendered state/disabled/native control |
| 1.4.4 Resize text | Relative typography and wrapping layout | Source only | Actual 200% browser zoom |
| 1.4.10 Reflow | Responsive shell, wrapping forms/cards, contained table scrolling | Search/candidates at 320px: document width 305px; table 238px viewport / 808px content | All pages and zoom combinations |
| 1.4.11 Non-text contrast | Separate high-contrast control borders and focus token | Calculated control/focus pairs | Complete rendered UI indicator audit |
| 2.1.1 Keyboard | Native links/buttons/inputs/selects/details; Admin switcher corrected to button group | Source; no full keyboard traversal | All keyboard workflows |
| 2.4.1 Bypass blocks | Skip link is first focusable page element; main target focusable | Source and DOM order | Manual Tab/Enter activation |
| 2.4.3 Focus order | DOM order follows shell/content order | Source only | Full keyboard sequence and form/task changes |
| 2.4.6 Headings/labels | Visible labels, page h1, section hierarchy, named table regions | Patient views and source | Every form/role |
| 2.4.7 Focus visible | 3px outline, 4px offset | Focus outline observed after login validation; computed contrast | Full keyboard focus audit |
| 2.4.11 Focus not obscured (minimum) | No new floating/fixed overlay except skip link | Source, limited patient views | All scroll/focus states |
| 2.5.8 Target size (minimum) | Most controls min-height 44px; checkboxes 24px with spacing | CSS inspected | Full target/spacing measurement |
| 3.3.1 Error identification | Error feedback uses visible text/alert | Wrong password and frontend tests | Every staff validation/error |
| 3.3.2 Labels/instructions | Native labels and descriptive action wording | Source/patient DOM | All screens |
| 4.1.2 Name/role/value | Native controls, aria-current, disclosure; Admin uses aria-pressed button group | Source and limited DOM snapshots | Real screen reader and Admin browser check |
| 4.1.3 Status messages | Loading live text, error alert, success status | Component tests; loading/error browser states | Assistive-technology announcements |

Reduced-motion and prefers-contrast CSS are present, and Admin edit scrolling chooses automatic behavior when reduced motion is requested; OS preference rendering is unverified. No screen reader, axe scan or real mobile device was used. DOM inspection and contrast calculations are automated/source evidence, not manual assistive-technology evidence.

## Shared tokens

All colors live in frontend/app/globals.css. Coral is used by primary actions; ordinary links/navigation/status colors use neutral or semantic tokens. Body is 16px/1.6; labels/table headings are 14px. KPI numerals are 2.5rem, semibold/tabular. Spacing tokens are 4/8/12/16/24/32px, card radius 12px, subtle shadow, focus 3px with 4px offset. Dashboard grid is four columns at ≥1024px, two at 640–1023px, one below 640px; cards fit content. Those grid rules are source-inspected; the admin four-KPI layout was not manually rendered after the browser stop.

| Token | Final color |
|---|---|
| bg | #0D1726 |
| surface | #16243A |
| surface-hover | #21344E |
| text | #F7F4EC |
| muted | #B8C2CF |
| line | #526781 |
| control | #8093AA |
| accent | #FF8B78 |
| accent-hover | #FFA391 |
| accent-text | #0D1726 |
| focus | #B9DCFF |
| warn | #F1CE83 |
| warn-bg | #342C19 |
| err | #FFB4BC |
| err-bg | #3C202D |
| ok | #9BDFB1 |
| ok-bg | #193329 |
| in / low / out | aliases of ok / warn / err |

Higher-contrast media mode changes line to #8093AA and control to #B8C2CF. Motion token is 120ms; no decorative animation was added.

## Computed actual combinations

Command: python scripts/check_contrast.py. **35/35 passed** their stated calculation thresholds. sRGB relative luminance: linearize each channel, L = 0.2126R + 0.7152G + 0.0722B; ratio = (Llighter + 0.05)/(Ldarker + 0.05).

| Use | Foreground/background | Ratio | Target |
|---|---|---:|---:|
| text | text #F7F4EC / bg #0D1726 | 16.363:1 | 4.5:1 |
| text | text #F7F4EC / surface #16243A | 14.178:1 | 4.5:1 |
| text | text #F7F4EC / surface-hover #21344E | 11.469:1 | 4.5:1 |
| text | muted #B8C2CF / bg #0D1726 | 9.982:1 | 4.5:1 |
| text | muted #B8C2CF / surface #16243A | 8.650:1 | 4.5:1 |
| text | muted #B8C2CF / surface-hover #21344E | 6.997:1 | 4.5:1 |
| text | ok #9BDFB1 / bg #0D1726 | 11.633:1 | 4.5:1 |
| text | ok #9BDFB1 / surface #16243A | 10.080:1 | 4.5:1 |
| text | ok #9BDFB1 / surface-hover #21344E | 8.154:1 | 4.5:1 |
| text | warn #F1CE83 / bg #0D1726 | 11.901:1 | 4.5:1 |
| text | warn #F1CE83 / surface #16243A | 10.312:1 | 4.5:1 |
| text | warn #F1CE83 / surface-hover #21344E | 8.342:1 | 4.5:1 |
| text | err #FFB4BC / bg #0D1726 | 10.711:1 | 4.5:1 |
| text | err #FFB4BC / surface #16243A | 9.281:1 | 4.5:1 |
| text | err #FFB4BC / surface-hover #21344E | 7.508:1 | 4.5:1 |
| input text | text #F7F4EC / bg #0D1726 | 16.363:1 | 4.5:1 |
| primary action | accent-text #0D1726 / accent #FF8B78 | 7.893:1 | 4.5:1 |
| primary hover | accent-text #0D1726 / accent-hover #FFA391 | 9.335:1 | 4.5:1 |
| success feedback | ok #9BDFB1 / ok-bg #193329 | 8.781:1 | 4.5:1 |
| verification status | warn #F1CE83 / warn-bg #342C19 | 9.140:1 | 4.5:1 |
| error/destructive action | err #FFB4BC / err-bg #3C202D | 8.706:1 | 4.5:1 |
| control boundary | control #8093AA / bg #0D1726 | 5.714:1 | 3:1 |
| control boundary | control #8093AA / surface #16243A | 4.951:1 | 3:1 |
| control boundary | control #8093AA / surface-hover #21344E | 4.005:1 | 3:1 |
| control boundary | control #8093AA / err-bg #3C202D | 4.644:1 | 3:1 |
| control boundary | control #8093AA / warn-bg #342C19 | 4.388:1 | 3:1 |
| control boundary | control #8093AA / ok-bg #193329 | 4.313:1 | 3:1 |
| offset focus outline | focus #B9DCFF / bg #0D1726 | 12.627:1 | 3:1 |
| offset focus outline | focus #B9DCFF / surface #16243A | 10.941:1 | 3:1 |
| offset focus outline | focus #B9DCFF / surface-hover #21344E | 8.851:1 | 3:1 |
| offset focus outline | focus #B9DCFF / err-bg #3C202D | 10.263:1 | 3:1 |
| offset focus outline | focus #B9DCFF / warn-bg #342C19 | 9.698:1 | 3:1 |
| offset focus outline | focus #B9DCFF / ok-bg #193329 | 9.532:1 | 3:1 |
| active navigation indicator | text #F7F4EC / surface-hover #21344E | 11.469:1 | 3:1 |
| primary button boundary | accent #FF8B78 / surface #16243A | 6.839:1 | 3:1 |

The focus ring is offset into the surrounding surface, so those adjacent surface pairs are evaluated. The subtle line token is for decorative card/table separators, not the sole control boundary. Disabled opacity/native popup rendering was not certified. See [browser evidence/limits](BROWSER_VERIFICATION.md).

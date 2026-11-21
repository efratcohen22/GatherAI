# Design system

Calm, organized, warm. Tokens live in `apps/web/src/styles/tokens.css` and map to Tailwind names.

| Token | Value |
|---|---|
| primary | #7258E8 |
| primary-strong | #4935A8 (text and buttons on white, meets AA) |
| lavender | #F1EDFF |
| ink | #202338 |
| canvas | #FAFAFD |
| surface | #FFFFFF |
| muted | #F3F4F8 |
| success | #147356 (darkened from #198765 to meet AA on white and soft green, D10) |
| warning | #E7A447 (fill only; pair with dark text) |
| danger | #D95362 |

Type: Inter for Latin, Heebo for Hebrew. Scale: 12, 14, 16, 20, 24, 32, 48.

Status is always shown with text, never color alone. Dark mode is prepared by keeping all colors in tokens. RTL is prepared through `src/i18n` and logical Tailwind properties.

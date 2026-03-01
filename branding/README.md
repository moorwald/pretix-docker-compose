# MautiCon 2026 - Pretix Branding

Custom CSS for the Pretix ticket shop to match the Mautic World Conference landing page design.

## How to Apply

1. Log into Pretix Admin: `tickets.mautic.org/control`
2. Navigate to: **Events > MautiCon 2026 > Settings > Display**
3. Scroll to **Custom CSS**
4. Paste the contents of `mauticon-pretix.css`
5. Save

## Updating

When changing the design:
1. Edit `mauticon-pretix.css` in this repo (source of truth)
2. Commit and push
3. Copy the updated CSS into Pretix Admin Panel

## Design Reference

Colours and typography match the landing page repo: `moorwald/mautic-world-conference`

| Token | Value | Usage |
|-------|-------|-------|
| `--mautic-gold` | `#fdb933` | Primary accent, headlines, CTAs |
| `--mautic-teal` | `#00b49d` | Secondary accent, success states |
| `--mautic-mondo` | `#4f3d31` | Warm dark brown |
| `--bg-dark` | `#1a1412` | Page background |
| `--bg-card` | `#2a2320` | Card/panel backgrounds |
| `--text-secondary` | `#a89a8c` | Muted text |

Fonts: Titillium Web (headlines), Roboto (body), IBM Plex Mono (code/badges).

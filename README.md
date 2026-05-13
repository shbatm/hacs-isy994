# hacs-isy994 — archived

> **🛑 This repository is archived and no longer maintained.**

This integration was a beta-testing ground for changes to the Home Assistant Core `isy994` integration, targeting **Universal Devices ISY-994** controllers (and the early IoX 5.x firmware that ran on the same hardware).

Active development has moved to a new repository for **eisy / Polisy on IoX 6+** hardware:

### → **[shbatm/hacs-udi-iox](https://github.com/shbatm/hacs-udi-iox)**

The new integration registers under the HA domain `udi_iox` (not `isy994`), uses the new [`pyisyox`](https://github.com/shbatm/pyisyox) v6 library (WebSocket-first, JSON API), and is built for IoX 6+ devices. It coexists with the legacy core `isy994` integration on the same HA instance — no domain collision.

## If you're running this integration

### You're on eisy / Polisy with IoX 6.x+

Switch to [`hacs-udi-iox`](https://github.com/shbatm/hacs-udi-iox). The new integration is feature-equivalent and where every bug fix and new feature lands going forward.

### You're on an ISY-994 (legacy hardware)

`hacs-udi-iox` does **not** support ISY-994 hardware (`pyisyox` 6.x dropped the legacy XML surfaces).

Two paths:

1. **Keep this integration installed.** It will continue to work for as long as your HA version's API surface stays compatible with the code in this repo, but no fixes will be shipped. **If something breaks**, your options are to either uninstall and revert to Home Assistant Core's built-in [`isy994` integration](https://www.home-assistant.io/integrations/isy994/), or install `hacs-udi-iox` (which won't talk to ISY-994 hardware).
2. **Switch to the HA Core integration now.** It tracks `pyisy` 3.x and is the supported long-term home for ISY-994 owners.

## Why archive?

The IoX 6 rewrite (eisy / Polisy) changed the controller's API surface end-to-end — a clean break was easier to maintain than dragging the legacy paths along. Continuing to develop two integrations in one repo (one for the ISY-994 wire format, one for IoX 6) created merge conflicts, ambiguous bug reports, and forced every PR to think about both code paths. Splitting the repos lets each track its own library version and devices.

## History

- **v1.x–v3.x**: tracked `pyisy` 1.x–3.x; intended as an upstream feed for the HA Core `isy994` integration.
- **v4.x**: tracked the `pyisyox` rewrite; the new wire surface eventually outgrew the upstream contribution path, motivating the split into a separate domain.

For the long-form change history, see the [CHANGELOG](CHANGELOG.md).

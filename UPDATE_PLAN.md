# HACS ISY994 Update Plan

**Created:** 2025-12-24
**Last Updated Since:** July 6, 2023
**Target:** Current Home Assistant standards (2024-2025)

This document outlines the changes needed to bring this HACS component up to current Home Assistant standards and practices.

---

## Executive Summary

The integration is well-structured but requires updates in these areas:

| Priority | Category | Impact | Effort |
|----------|----------|--------|--------|
| **Critical** | Replace `async_timeout` with `asyncio.timeout()` | Breaking in future HA | Low |
| **Critical** | Add event listener cleanup | Memory leak prevention | Low |
| **High** | Migrate to `entry.runtime_data` | Modern pattern | Medium |
| **High** | Update ServiceInfo imports | Deprecated location | Low |
| **Medium** | Config flow modernization | Better UX | Medium |
| **Medium** | Type hint improvements | Code quality | Medium |
| **Low** | EntityDescription consistency | Best practices | Low |

---

## Critical Priority

### 1. Replace `async_timeout` with `asyncio.timeout()`

**Files affected:**
- `__init__.py` (line 8, 111)
- `config_flow.py` (line 10, 104)

**Before:**
```python
import async_timeout
...
async with async_timeout.timeout(60):
```

**After:**
```python
import asyncio
...
async with asyncio.timeout(60):
```

**Reference:** Python 3.11+ includes `asyncio.timeout()` natively. The `async_timeout` library is deprecated.

---

### 2. Add Event Listener Cleanup

**Files affected:**
- `entity.py` (ISYEntity, ISYNodeEntity classes)

**Issue:** Event handlers subscribed in `async_added_to_hass()` are never unsubscribed.

**Fix:** Add `async_will_remove_from_hass()` method:

```python
async def async_will_remove_from_hass(self) -> None:
    """Unsubscribe from node events."""
    if self._change_handler:
        self._change_handler.unsubscribe()
```

For `ISYNodeEntity`, also unsubscribe `_availability_handler`.

---

## High Priority

### 3. Migrate from `hass.data` to `entry.runtime_data`

**Files affected:** All platform files and `__init__.py`

**Reference:** [Blog post - April 30, 2024](https://developers.home-assistant.io/blog/2024/04/30/config-entry-runtime-data/)

**Changes in `__init__.py`:**

**Before:**
```python
hass.data.setdefault(DOMAIN, {})
isy_data = hass.data[DOMAIN][entry.entry_id] = IsyData()
```

**After:**
```python
isy_data = IsyData()
entry.runtime_data = isy_data
```

**In platform files, replace:**
```python
isy_data = hass.data[DOMAIN][entry.entry_id]
```

**With:**
```python
isy_data: IsyData = entry.runtime_data
```

**Type hints:** Update `models.py` to define a custom ConfigEntry type:
```python
from homeassistant.config_entries import ConfigEntry as HAConfigEntry

type IsyConfigEntry = HAConfigEntry[IsyData]
```

---

### 4. Update ServiceInfo Imports

**Files affected:**
- `config_flow.py` (lines 21)

**Reference:** [Blog post - January 15, 2025](https://developers.home-assistant.io/blog/2025/01/15/service-info-models/)

**Before:**
```python
from homeassistant.components import dhcp, ssdp
...
discovery_info: dhcp.DhcpServiceInfo
discovery_info: ssdp.SsdpServiceInfo
```

**After:**
```python
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
...
discovery_info: DhcpServiceInfo
discovery_info: SsdpServiceInfo
```

**Deprecation:** Old locations will be removed in HA 2026.2.

---

## Medium Priority

### 5. Config Flow Modernization

**Files affected:**
- `config_flow.py`

**Changes:**
1. Use `_get_reauth_entry()` helper instead of manual tracking:
   ```python
   async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
       """Handle reauth."""
       return await self.async_step_reauth_confirm()

   async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
       entry = self._get_reauth_entry()  # New helper
       ...
   ```

2. Consider implementing `async_step_reconfigure()` for settings changes.

3. Add `_abort_if_unique_id_mismatch()` validation in reauth flows.

---

### 6. Type Hint Improvements

**Files affected:**
- `models.py`
- `helpers.py`
- Various platform files

**Changes:**
1. Add complete type annotations to `IsyData` fields
2. Use `field(default_factory=...)` for mutable defaults
3. Add return type hints to all public methods

**Example for `models.py`:**
```python
from dataclasses import dataclass, field

@dataclass
class IsyData:
    """Data class for ISY integration runtime data."""
    root: ISY | None = None
    nodes: dict[str, list[Node]] = field(default_factory=dict)
    groups: list[Group] = field(default_factory=list)
    # ... etc
```

---

### 7. Options Flow Constructor Update

**Files affected:**
- `config_flow.py` (line 305-307)

**Before:**
```python
class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
```

**After:**
```python
class OptionsFlowHandler(config_entries.OptionsFlow):
    # No __init__ needed - self.config_entry is automatically available
    pass
```

---

## Low Priority

### 8. EntityDescription Consistency

**Files affected:**
- `light.py` (doesn't use EntityDescription)

All other platform files use `EntityDescription` subclasses. Consider adding `LightEntityDescription` to `light.py` for consistency.

---

### 9. Icon Range Support

**Files affected:**
- Consider adding `icons.json` for battery/signal sensors

**Reference:** [Blog post - May 22, 2025](https://developers.home-assistant.io/blog/2025/05/22/icon-range/)

New feature allows defining icon ranges without custom code.

---

### 10. FlowResult Import Update

**Files affected:**
- `config_flow.py` (line 24)

**Before:**
```python
from homeassistant.data_entry_flow import AbortFlow, FlowResult
```

**After:**
```python
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.data_entry_flow import AbortFlow
```

Use `ConfigFlowResult` instead of generic `FlowResult`.

---

## Manifest Updates

**File:** `manifest.json`

Current:
```json
{
  "requirements": ["pyisyox==1.0.0a10"],
  "version": "4.0.16"
}
```

Considerations:
1. Update `pyisyox` version if newer releases are available
2. Bump version after updates
3. Consider adding `"quality_scale"` field if applicable

---

## Testing Requirements

After implementing changes, test:

1. **Fresh installation** - Config flow creates entry correctly
2. **Reauth flow** - Credentials update works
3. **Options flow** - Settings changes reload properly
4. **Entity creation** - All platforms load entities
5. **Event updates** - WebSocket events update entity states
6. **Unload** - Clean unload without memory leaks
7. **Discovery** - DHCP and SSDP discovery work

---

## Breaking Changes to Monitor

These HA deprecations have extended timelines but should be tracked:

| Deprecation | Removal Date | Action Needed |
|-------------|--------------|---------------|
| ServiceInfo imports | 2026.2 | Update imports |
| `hass.helpers` attribute | 2025.5 | Verify not used |
| `async_track_state_change` | 2025.5 | Verify not used |

---

## Differences from Core Integration

This HACS component intentionally differs from the Core `isy994` integration:

| Aspect | Core | HACS |
|--------|------|------|
| Library | `pyisy==3.4.1` | `pyisyox==1.0.0a10` |
| Purpose | Stable, conservative | Beta testing, new features |
| Updates | HA release cycle | Independent releases |

The `pyisyox` library is a modernized fork/rewrite of `pyisy`. Changes in this HACS component may eventually be ported to Core after stabilization.

---

## Implementation Order

Recommended order of implementation:

1. **Phase 1 - Critical fixes** (can be done immediately)
   - Replace `async_timeout`
   - Add event listener cleanup

2. **Phase 2 - High priority modernization**
   - Migrate to `entry.runtime_data`
   - Update ServiceInfo imports

3. **Phase 3 - Medium priority improvements**
   - Config flow modernization
   - Type hint improvements

4. **Phase 4 - Low priority enhancements**
   - EntityDescription consistency
   - Icon range support

---

## References

- [Home Assistant Developer Blog](https://developers.home-assistant.io/blog/)
- [Core ISY994 Integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/isy994)
- [HA Core Copilot Instructions](https://github.com/home-assistant/core/blob/dev/.github/copilot-instructions.md)
- [Config Entry Runtime Data](https://developers.home-assistant.io/blog/2024/04/30/config-entry-runtime-data/)

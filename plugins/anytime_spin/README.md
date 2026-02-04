# Anytime Spin Plugin

This plugin enables the spin feature (normally only available on Sundays) to work any day of the week.

## How it works

MBII's spin feature checks the system day of the week and only enables on Sundays. This plugin uses `LD_PRELOAD` to intercept the `localtime()` system call and always return Sunday as the day of week.

## Setup

1. Place `fake_sunday_32.so` in this folder (`plugins/anytime_spin/`)
2. Add to your instance config under `plugins`:

```json
{
  "plugins": {
    "anytime_spin": {}
  }
}
```

### Related Game Settings

You'll also want these in your `game` section:

| Setting | Type | Description |
|---------|------|-------------|
| `enable_spin` | int | 0 = disabled, 1 = enabled (g_spin cvar) |
| `spin_cooldown` | int | Cooldown in seconds between spins (g_SpinCooldown cvar) |

## Building fake_sunday_32.so

If you need to rebuild the library:

```c
// fake_sunday.c
#define _GNU_SOURCE
#include <time.h>
#include <dlfcn.h>

struct tm *localtime(const time_t *timep) {
    static struct tm *(*real_localtime)(const time_t *) = NULL;
    if (!real_localtime) {
        real_localtime = dlsym(RTLD_NEXT, "localtime");
    }
    struct tm *result = real_localtime(timep);
    if (result) {
        result->tm_wday = 0;  // 0 = Sunday
    }
    return result;
}

struct tm *localtime_r(const time_t *timep, struct tm *result) {
    static struct tm *(*real_localtime_r)(const time_t *, struct tm *) = NULL;
    if (!real_localtime_r) {
        real_localtime_r = dlsym(RTLD_NEXT, "localtime_r");
    }
    struct tm *ret = real_localtime_r(timep, result);
    if (ret) {
        ret->tm_wday = 0;  // 0 = Sunday
    }
    return ret;
}
```

Compile for 32-bit (MBII server is 32-bit):
```bash
gcc -m32 -shared -fPIC -o fake_sunday_32.so fake_sunday.c -ldl
```

## Notes

- The `fake_sunday_32.so` library must be 32-bit since the MBII dedicated server is 32-bit
- This only affects the game server process, not the rest of your system
- You still need to set `enable_spin: 1` and `spin_cooldown` in your config for spin to work

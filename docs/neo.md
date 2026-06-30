# Neo Backend

The Neo backend targets the modern Windows Steam executable:

```text
File: SuperHexagon.exe
SHA-256: 72b0c26053c37edd3435def461e9027cd6ffad12032db2fd0b32c256fdbee6b9
Size: 1467904 bytes
```

It keeps simulation timing at the original cadence, raises render pacing, and
interpolates selected visual fields during draw. Existing legacy patch states
from earlier experiments are detected so users can migrate cleanly.

Default menu choices:

```text
120, 240, 480
```

Any multiple of `60` from `120` upward is accepted from the command line or the
menu's custom option. Very high modes are experimental and depend on the display,
driver, and system pacing.

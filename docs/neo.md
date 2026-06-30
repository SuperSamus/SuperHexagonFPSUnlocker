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

Supported public patch choices:

```text
120, 180, 240, 300, 360
```

`120` and `240` are the known stable targets. Higher modes are available for
testing on high refresh displays.


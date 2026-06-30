# pre-Neo Backend

The pre-Neo backend targets the older Windows Steam executable:

```text
File: superhexagon.exe
SHA-256: 69411cb275202b21c3e0428a5c27704e97663a17723497b61bd7dfeaa1534bdd
Size: 2698240 bytes
```

The pre-Neo build has a different GLUT/openFrameworks timing loop. The backend
keeps the 16 ms simulation cadence and interpolates final wall draw coordinate
arrays between simulation ticks. The original values are restored immediately
after draw so logical game state remains untouched.

Supported public patch choices:

```text
120, 180, 240, 300, 360, 960
```

`120` and `240` are the known stable targets. Other multiples of 60 are exposed
for testing, but should be validated in actual levels.

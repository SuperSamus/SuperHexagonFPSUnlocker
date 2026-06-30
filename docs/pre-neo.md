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

Default menu choices:

```text
120, 240, 480
```

Any multiple of `60` from `120` upward is accepted from the command line or the
menu's custom option. Very high modes should be validated in actual levels.

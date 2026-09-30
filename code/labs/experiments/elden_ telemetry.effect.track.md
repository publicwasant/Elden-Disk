```commandline
PS D:\StudioProjects\Elden-Ring-Telemetry-Tools\code>    python -m elden_telemetry effects
Ctrl+C to stop. Format: id | duration | timer   (+ = appeared, - = disappeared)
--- 8 effects now active ---
        1940 |      -1.00 |      -1.00
      100621 |      -1.00 |      -1.00
      310210 |      -1.00 |      -1.00
      311100 |      -1.00 |      -1.00
      320500 |      -1.00 |      -1.00
      350200 |      -1.00 |      -1.00
      503045 |       0.10 |       0.10
      503360 |      -1.00 |      -1.00
-     311100                                    <-- When I remove Gold Scarab
+     311100 |      -1.00 |      -1.00          <-- When I equip Gold Scarab
+       3971 |     180.00 |     179.60          <-- When I use Gold-Pickled Fowl Foot, very clearly duration is 180s that mean 3.0m
+     100001 |       0.00 |       0.00
+     100006 |       0.00 |       0.00
-     100001
-     100006
+       1922 |      -1.00 |      -1.00
+     100620 |      -1.00 |      -1.00
-       1940
-     100621
+     100150 |       0.00 |       0.00
-     100150
+    1605000 |      30.00 |      29.93          <-- When I spell Flame! Grant Me Strength, duration is 30s
+    1605001 |       0.10 |       0.10
+    1605002 |       0.10 |       0.07
+    1660000 |      80.00 |      79.77          <-- When I spell Golden Vow, duration is 80s
+    1660001 |       0.10 |       0.07
+    1660002 |       0.10 |       0.07
-    1605000
-    1605001
-    1605002
-    1660000
-    1660001
-    1660002
-       1922
-       3971
-     100620
-     310210
-     311100
-     320500
-     350200
-     503045
-     503360
PS D:\StudioProjects\Elden-Ring-Telemetry-Tools\code>
```

### Tracking Results
|      ID | Name                     |
|--------:|:-------------------------|
|  311100 | Gold Scarab              |
|    3971 | Gold-Pickled Fowl Foot   |
| 1605000 | Flame! Grant Me Strength |
| 1660000 | Golden Vow               |

```commandline
PS D:\StudioProjects\Elden-Disk\build\dist\eldendisk> .\eldendisk.exe read --query character.buffs.* --live  
 Elden-Disk 1.6.4 · read
 ────────────────────────────────────────────────────────────────
   game     eldenring.exe, pid 14028
   profile  Elden Ring 1.17.1
   mode     character.buffs.* (live)
 ────────────────────────────────────────────────────────────────
 19:00:58  ✓  read   attached, reading (Ctrl+C to stop)
 character
   buffs
     311100
       name        Gold Scarab
       categories  TALISMANS
       abilities   Permanently increases Runes gained by 20% while equipped.
 19:01:43  ·  read   stopped; the game keeps running
 ```

```commandline
PS D:\StudioProjects\Elden-Disk\build\dist\eldendisk> .\eldendisk.exe read --live-buffs                    
 Elden-Disk 1.6.4 · read
 ────────────────────────────────────────────────────────────────
   game     eldenring.exe, pid 14028
   profile  Elden Ring 1.17.1
   mode     buffs (live)
 ────────────────────────────────────────────────────────────────
 19:01:54  ✓  read   attached, reading (Ctrl+C to stop)
 buffs   9 active · 13 seen · 12 unmapped
           id  name         timer         time
 +  999999999  Unknown      5.1 / 15.0 s  19:02:23.746 <--- # Reverse Cursed Technique, ID 999999999 Not Exist in chr_state_ids.json;
 +       1922  Unknown      permanent     19:01:54.137
 +     100620  Unknown      permanent     19:01:54.137
 +     310210  Unknown      permanent     19:01:54.137
 +     311100  Gold Scarab  permanent     19:01:54.137
 +     320500  Unknown      permanent     19:01:54.137
 +     350200  Unknown      permanent     19:01:54.137
 +     503045  Unknown      0.1 / 0.1 s   19:01:54.137
 +     503360  Unknown      permanent     19:01:54.137
 -     100610  Unknown                    19:02:23.063
 -     100006  Unknown                    19:02:22.080
 -     100000  Unknown                    19:02:20.913
 -     100001  Unknown                    19:02:20.880
```

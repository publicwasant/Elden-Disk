# Item-customization tools

Everything needed to reproduce the build described in `../item-customization-handbook.md`.

```
pip install cryptography zstandard
git clone https://github.com/soulsmods/Paramdex.git && git -C Paramdex checkout ff7245e5
copy <ELDEN RING>\Game\regulation.bin  regulation.orig.bin      # pristine 1.17.1 copy, 2,045,728 bytes
python selftest.py          # offline checks, no game needed
python make_item.py --name Z1                # Y1 reproduction
python make_item.py --name Z4 --faith 15 --intellect 45 --arcane 10 --fp-cost 80 --price 34590 --motion 32 --poise-sp 102006   # final item
```

Output: `out/regulation.<name>.bin`. Offline play only; back up the original first. See Appendix E of the handbook for a file index.

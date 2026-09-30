"""Lab 5: signature (AOB) scan + RIP-relative resolution on a SYNTHETIC image.

The numbers are made up so that the instruction resolves to RVA 0x3B16E30
(the real profile value). No real Elden Ring pattern is claimed here.
"""
import re
import struct


def compile_aob(pattern: str) -> re.Pattern:
    """'48 8B 05 ?? ?? ?? ??' -> compiled byte regex ('??' = any byte)."""
    parts = []
    for tok in pattern.split():
        parts.append(b"." if tok in ("??", "?") else re.escape(bytes([int(tok, 16)])))
    return re.compile(b"".join(parts), re.DOTALL)


def resolve_rip_relative(image: bytes, match_off: int, disp_off: int, instr_len: int) -> int:
    """Target RVA of an instruction like `mov rax, [rip+disp32]`.

    target = (address of NEXT instruction) + signed disp32
           = match_off + instr_len + disp32          (all as RVAs)
    """
    disp = struct.unpack_from("<i", image, match_off + disp_off)[0]
    return match_off + instr_len + disp


def find_unique(image: bytes, pattern: str) -> int:
    hits = [m.start() for m in compile_aob(pattern).finditer(image)]
    if len(hits) != 1:
        raise LookupError(f"pattern matched {len(hits)} times (need exactly 1)")
    return hits[0]


if __name__ == "__main__":
    INSTR_RVA, TARGET_RVA = 0x1A2B3C0, 0x3B16E30
    image = bytearray(0x1A2B500)                       # fake .text, all zeros
    disp = TARGET_RVA - (INSTR_RVA + 7)                # 7 = length of `48 8B 05 <disp32>`
    # mov rax,[rip+disp32] ; test rax,rax ; jz +0F   (a plausible "singleton check" shape)
    code = bytes([0x48, 0x8B, 0x05]) + struct.pack("<i", disp) + bytes([0x48, 0x85, 0xC0, 0x74, 0x0F])
    image[INSTR_RVA:INSTR_RVA + len(code)] = code

    at = find_unique(bytes(image), "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 0F")
    rva = resolve_rip_relative(bytes(image), at, disp_off=3, instr_len=7)
    print(f"pattern found at RVA 0x{at:X}; disp32 = 0x{disp:X}; resolved RVA = 0x{rva:X}")
    assert at == INSTR_RVA and rva == TARGET_RVA
    print("OK")

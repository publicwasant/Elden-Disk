# Animation State Verification

According to the **vswarte/fromsoftware-rs (crate Elden-Ring)** repository, this is the best reference because they have successfully mapped out the memory layout of the **ChrIns** module. You can check the source code in **[chr_ins.rs](https://github.com/vswarte/fromsoftware-rs/blob/main/crates/eldenring/src/cs/chr_ins.rs)**.

However, I needed to prove this myself in-game (v1.17.1). I decided to manually verify this by reading the values at the given addresses step-by-step to ensure it actually works as expected.

> [!NOTE]
> **Tools:** Cheat Engine v7.7      
> **Function:** Add Address Manually       
> **Base:** `"eldenring.exe"+3B16E30`

| **In-game actions**                                    | **Pointers: [90, 18, 190, 0]** | **Pointers: [50, 18, 190, 0]** |
|:-------------------------------------------------------|:-------------------------------|:-------------------------------|
| Just standing                                          | 2000000                        | 2000000                        |
| Running                                                | 2020110                        | 2020110                        |
| Sprinting                                              | 2020210                        | 2020210                        |
| Rolling                                                | 27110                          | 27110                          |
| Attacking (R1)                                         | 26030000                       | 26030000                       |
| Pause while standing                                   | 2000000                        | 2000000                        |
| Resting at Site of Grace (Palace Approach Ledge-Road)  | 68011                          | 68011                          |
| Resting at Site of Grace (Dynasty Mausoleum Entrance)  | 68011                          | 68011                          |
| Resting at Site of Grace (Dynasty Mausoleum Midpoint)  | 68011                          | 68011                          |
| Resting at Site of Grace (Church of Elleh)             | 68011                          | 68011                          |
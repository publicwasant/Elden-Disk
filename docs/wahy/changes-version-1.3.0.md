# Changes

> [!NOTE]
> **Summary:** Refactored project/package to `Elden-Disk`/`eldendisk`/`disk`, added `IDLE` state with window focus detection, implemented 60FPS pacing & Event-Driven Persistence Architecture, removed `timestamp`, and passed all v1.3.0 unit tests.    
> **Status:** APPROVED ✔    
> **Last Updated:** _2026-10-01_

_(Previous version: Wahy: **[changes-version-1.2.1.md](changes-version-1.2.1.md)** and the spec: **[elden-telemetry-spec-v1.2.1.md](../specs/elden-telemetry-spec-v1.2.1.md)**)_

---

## Murmur

"The concept is a very lightweight **Memory Read Tool** featuring an **Event-Driven Persistence Architecture**, now boasting the coolest codename." — Words of murmur, Me.

### Stage 1: Naming

I am the one who originally named this project **Elden-Ring-Telemetry-Tools** (or **Elden_Telemetry**), and here is my confession: I absolutely hate that damn name every time I come back to the project—even though I'm the one who came up with it.

The word "Telemetry". What does that even mean in this context? What is it trying to tell the world? I don't even remember how that word popped into my head.

Look, I'm not just hating on the project's naming for no reason. But it could definitely be better.

**Here is what I figured out after staying with this project for a while:**

| **New Repository Name** | **How the CLI Command Looks** | **Reason**                                              |
|:------------------------|:------------------------------|:--------------------------------------------------------|
| **Elden-Read**          | **`eldenread.exe run -v`**    | Simple, readable, and understandable. (I think)         |
| **Elden-Disk**          | **`eldendisk.exe run -v`**    | I have no idea what it means, but it looks cool, right? |

Anyway, I've decided to go with **EldenDisk**, and once it becomes a production-ready single `.exe` release, it will be: **eldendisk.exe**.

**CLI Commands (can be used as a library):**
- **`eldendisk.exe hash`**
- **`eldendisk.exe run -v`**
- **`eldendisk.exe run --attach`**
- **`eldendisk.exe effects -q`**

### Stage 2: State Machine

According to **[elden-telemetry-spec-v1.2.1.md](../specs/elden-telemetry-spec-v1.2.1.md)** in the **4.6 Connection state machine** we have:

| **State**                     | **Meaning**                                                  | **JSON `character`** |
|:------------------------------|:-------------------------------------------------------------|:--------------------:|
| `WAITING_FOR_PROCESS`         | Game not running                                             |        `null`        |
| `EAC_ACTIVE` / `EAC_DETECTED` | EAC present; tool refuses to attach                          |        `null`        |
| `UNSUPPORTED_VERSION`         | Exe hash not in `offsets.json`                               |        `null`        |
| `WAITING_FOR_WORLD`           | Process up but pointer chain is null (title screen, loading) |        `null`        |
| `CONNECTED`                   | All validations pass                                         |     full object      |
| `DISCONNECTED`                | Process exited                                               |        `null`        |

Think about it.

Let it sink in... we are missing a critically important state! We need an **`IDLE`** state. Without it, our tool is running the loop *every single damn tick*, completely ignoring whether the game window is even active or in focus. Again, this doesn't respect the game's pacing or system resources.

It is much better to run the active process *only* when the game window is in focus. If we switch out of the game window, we should raise the **`IDLE`** state to freeze everything: no reading, no writing, and no processing. Just pause. Whenever we switch focus back to the game window, the sequence resumes its cycle automatically.

### Stage 3: Pacing

This is our recent workflow:

```text
[ Offline Launcher ] → [ Read-Only Memory Reader (version-pinned) ] → [ JSON Telemetry Output ]
```

It looks like a pretty simple sequence of processes: launch the game (offline), read stats from memory addresses using pointer chains, and write the results into a JSON file.

But look closer. The `[ Offline Launcher ]` is fine; nothing confusing there. However, there are two things we need to clarify:
- **Reading Process Frequency:** How many times per second should we read the memory? If it's faster than necessary, it doesn't align with the game's actual pacing.
- **Writing JSON Frequency:** How often should we write to the JSON file? If it updates faster than necessary, we basically become the villain—like slave owners whipping their slaves for no reason just to force them to work harder back in 1880. By the way, the point is this brute-force approach completely violates the concept of **Words of murmur**.

I've realized that blindly reading/writing the JSON file every single tick (real-time update) consumes way too many system resources, which completely contradicts the goal of building a **Very Lightweight Memory Read Tool** for sure.

Think about it: while playing the game (Elden Ring) on **Maximum Graphic Settings**, if we run heavy I/O read/writes continuously, my computer might actually crash out—and this is not a joke.

**What's wrong with the current workflow?:**
- **[ Offline Launcher ]** Works perfectly from the previous version. Nothing to change. Pass.
- **[ Read-Only Memory Reader (version-pinned) ]** According to **Bandai Namco’s specs**, _"On PC, Elden Ring’s frame-rate will be capped at 60fps." (Source: [videogameschronicle.com](https://www.videogameschronicle.com/news/elden-rings-performance-modes-confirmed-ray-tracing-to-come-via-patch/))_. With that pacing, we should lock our process to **READ 60 times per second**, matching the game's pacing. Right?
- **[ JSON Telemetry Output ]** In the previous version, we immediately wrote to disk right after receiving data from memory. Actually, we can't do that because the loop is way too heavy, even for a high-performance gaming PC. The tool must be as good as it should be.

So, I've decided to remake the workflow into this new sequence:

```text
[LAUNCH] → [READ MEMORY AND UPDATE STATE (In RAM) @ 60FPS LOCKED] → [JSON WRITE (To Disk)]
```

**Breakdown:**
- **[LAUNCH]** Change nothing.
- **[READ MEMORY AND UPDATE STATE (In RAM)]** We look up the game's memory addresses and read, then move the data to store it in our own memory block (In RAM) first. We bypass writing to any files and just hold it in our hands.
- **[JSON WRITE (To Disk)]** This is the protagonist of this section we're talking about. Previously, we eagerly wrote the JSON file immediately after receiving the data from memory. Now, we're not going to do that. Ladies and gentlemen, or whomever is reading, in this part I appreciate introducing the **Event-Driven Persistence Architecture** to police our computer resources.

The **Event-Driven Persistence Architecture** is a famous method used to reduce forced processing. We only write the JSON output file when it's absolutely necessary to write. For example: when we need to read the character's total runes, we first check if the recently read runes equal the previous runes stored in our disk block → do nothing. But if not, just execute a write to update the JSON file.

Or in advanced objects such as a **TIMED** effect, where it has a **`buff_duration`** that we need to monitor for the time left. In this case, we are allowed to repeatedly write to the JSON file until the time left runs out. But do not forget the **60FPS** pacing constraint—we're going to write at most 60 times per second.

---

## Wahyi

### 1. Replace All `Elden-Ring-Telemetry-Tools` → `Elden-Disk`

_(Scan the entire project—combing through every detail of the source code and package structures—to locate and replace all legacy naming references.)_

**Refactoring Target Mapping:**
- **Repository Name**: `Elden-Disk` (formerly `Elden-Ring-Telemetry-Tools`)
- **Python Code Package Name**: `eldendisk` (formerly `elden_telemetry`)
- **Files name**: `disk` (formerly `telemetry`)
- **Executable / Release Binary Name**: `eldendisk.exe`

### 2. Add New Connection State Machine

*(Introduce the `IDLE` state to the connection state machine)*

| **State**                     | **Meaning**                                                  | **JSON `character`** |
|:------------------------------|:-------------------------------------------------------------|:--------------------:|
| `WAITING_FOR_PROCESS`         | Game not running                                             |        `null`        |
| `EAC_ACTIVE` / `EAC_DETECTED` | EAC present; tool refuses to attach                          |        `null`        |
| `UNSUPPORTED_VERSION`         | Exe hash not in `offsets.json`                               |        `null`        |
| `WAITING_FOR_WORLD`           | Process up but pointer chain is null (title screen, loading) |        `null`        |
| `CONNECTED`                   | All validations pass                                         |   `<full-object>`    |
| `DISCONNECTED`                | Process exited                                               |        `null`        |
| `IDLE`                        | Game's window is not active                                  |   `<full-object>`    |

The core behavior of the `IDLE` state is to freeze the entire read/write loop—essentially putting **EldenDisk** into sleep mode—to eliminate unnecessary background processing. This saves the computer from that Red Bull-fueled, brute-force programming shit.

### 3. Integrate 60FPS Pacing and Event-Driven Persistence

*(Assuming you've read the Murmur's pacing section, I expect you already understand exactly what's going on here. In this section, we're going to expand on it.)*

**Forget everything you know about the previous sequence of processes, and wrap your head around this redesigned diagram:**

```text
[LAUNCH] → [READ MEMORY AND UPDATE STATE (In RAM) @ 60FPS LOCKED] → [JSON WRITE (To Disk)]

or, for short-term recognition:

[LAUNCH] → [READ] → [WRITE]
```

As I said before, **[LAUNCH]** is working perfectly—change nothing. Now, we're going to talk about the **[READ]** and **[WRITE]** mechanisms.

Regarding the memory reading specifications in **[elden-telemetry-spec-v1.2.1.md](../specs/elden-telemetry-spec-v1.2.1.md#4-memory-reading)**[cite: 4]: we are keeping the process strictly bound to this. That includes **Version pinning (offsets.json)**, the **Pointer chain**, the **Field table**, and the **Special effects (linked list) & Refactored `effects` Object**[cite: 4]. We are not changing *anything* in those sections because they are working perfectly, exactly as they should be.

However, to keep the mechanism of our tool aligned with the core concept of **A Very Lightweight Memory Read Tool**, we must integrate the two major methods I introduced earlier.

#### 3.1 60FPS Pacing

On PC, Elden Ring’s frame-rate is capped at 60fps, making it incredibly easy to sync the frequency of the game's pacing with our tool's reading mechanism. This means our loop will look like this:

```text
REPEATING PROCESS IN THREAD (60 Executions Per Second)
    └─► READ MEMORY ─────────────► UPDATE STATE (IN TOOL'S RAM)
```

#### 3.2 Event-Driven Persistence

Instead of writing the output immediately to the JSON file, we keep that data in our tool's RAM first. You know the base addresses. The pointer chain guides you like a holy treasure map, and when you reach the destination, you grab that treasure and hold it in your hand.

But when exactly do we *actually* need to write this data down?

**Check out this logic flow:**

```text
REPEATING PROCESS IN THREAD (60 Executions Per Second)
    └─► READ MEMORY ─────────────► UPDATE STATE (IN TOOL'S RAM)
                                      └─► STATE DIFF CHECKING LOGIC
                                            └─► IF TRUE (CHANGED) ────────► WRITE JSON FILE 
                                            └─► IF FALSE (UNCHANGED) ─────► DO NOTHING
```

> [!IMPORTANT]
> **Exception for Active Timers:** For objects classified as a **TIMED** effect, which feature an active **`buff_duration`** countdown. In this specific scenario, we are permitted to continuously write to the JSON file to reflect the ticking timer until the duration runs out. Even here, the **60FPS pacing constraint** must be strictly respected.

### 4. (Schema Update)

Remove the top-level `timestamp` field from the output schema in `/code/output/telemetry-state.json`. We simply do not need it anymore.

### 5. Requirements

#### 5.1 Documentations
- **New Specification Version `1.3.0`:**
    - Derived from:<br>[elden-telemetry-spec-v1.0.0.md](../specs/elden-telemetry-spec-v1.0.0.md)<br>[elden-telemetry-spec-v1.1.0.md](../specs/elden-telemetry-spec-v1.1.0.md)<br>[elden-telemetry-spec-v1.2.0.md](../specs/elden-telemetry-spec-v1.2.0.md)<br>[elden-telemetry-spec-v1.2.1.md](../specs/elden-telemetry-spec-v1.2.1.md)<br>**[NEW] elden-disk-spec-v1.3.0.md**
    - Save at `./docs/specs/elden-disk-spec-v1.3.0.md`
- **New Implementation Plan:**
    - Scan the whole project, every details of source cods and design a **implementation_plan_v1.3.0.md**.
    - Save at `./docs/impls/implementation_plan_v1.3.0.md`

#### 5.2 Integrations
- Development according to the **[elden-disk-spec-v1.3.0.md](../specs/elden-telemetry-spec-v1.2.1.md)** and the **[implementation_plan_v1.3.0.md](../implementations/implementation_plan_v1.2.1.md)**
- Verification by **Unit-Test**
- Update **Tool-Version** and all the documentations that exist the **Changes.**

---
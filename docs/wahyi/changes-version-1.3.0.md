# Changes

> [!NOTE]
> **Summary:** _Writing._     
> **Status:** _Writing._    
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
_(?????????????????)_

### 1. ?????????????????
### 2. ?????????????????

---
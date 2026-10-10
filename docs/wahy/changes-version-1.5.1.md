> [!NOTE]
> **Version:** `1.5.1`  
> **Status:** APPROVED ✔     
> **Last Updated:** _2026-10-04_

**Summary:** Introduces the `build` CLI command to compile the Elden-Disk project into a standalone single executable (`eldendisk.exe`), defines its dedicated CLI documentation, and establishes an automated End-to-End development pipeline.

_(baseline version: Wahy: **[changes-version-1.5.0.md](changes-version-1.5.0.md)** and the spec: **[elden-disk-spec-v1.5.0.md](../specs/elden-disk-spec-v1.5.0.md)**)_

---

## Murmur

"I am so done explaining to users how to install Python, set up environment variables, and run `pip install -r requirements.txt`. Half of them get an execution policy error, and the other half install it on Python 3.8. Just give me the damn `.exe` so they can double-click and be done with it!" — me

Distributing a Python application shouldn't be a nightmare. It's time to pack this entire telemetry machine into a single, standalone executable.

---

## Wahy

### 1. Introduce the `build` CLI command

To automate the compilation process, we are introducing a new CLI command. Running `python -m eldendisk build` will trigger the build pipeline, turning our Python modules into a single `eldendisk.exe` file located in the `./dist` folder.

**Usage:**
```commandline
python -m eldendisk build [OPTIONS]
```

**Available Options:**

| **Option** | **Alias** | **Type** | **Default** | **Description** |
|:---|:---:|:---:|:---|:---|
| `--engine` | `-e` | `enum` | `pyinstaller` | Choose the build engine. Options: `pyinstaller` (fast, standard) or `nuitka` (compiles to C/C++ for higher performance and reverse-engineering protection). |
| `--clean` | `-c` | `flag` | `False` | Clean the `./build` and `./dist` cache directories before compiling to ensure a fresh build. |
| `--embed-configs` | `-em` | `flag` | `False` | If passed, embeds `offsets.json` and `chr_state_ids.json` directly into the `.exe`. If omitted, the `.exe` will look for these files externally in the same directory, allowing users to update them without recompiling. |
| `--icon` | `-i` | `string` | `None` | Path to an `.ico` file to use as the application icon (e.g., `--icon assets/icon.ico`). |

### 2. Output and Distribution

After a successful build, the output mechanism will behave as follows:

```commandline
PS D:\StudioProjects\Elden-Disk\code> python -m eldendisk build -c --engine pyinstaller --icon assets/icon.ico
[INFO] Cleaning previous build artifacts...
[INFO] Initializing PyInstaller engine...
[INFO] Building eldendisk.exe (Onefile mode)...
[SUCCESS] Build complete! Standalone executable located at: ./dist/eldendisk.exe
```

> [!IMPORTANT]
> **Asset Handling (PyInstaller `_MEIPASS`):** When using `--embed-configs`, the source code must be updated to handle file paths dynamically. When running as a frozen `.exe`, the tool must read the bundled assets from the `sys._MEIPASS` temporary directory rather than the current working directory.

### 3. Executable CLI Commands Documentation

Since users will interact with `eldendisk.exe` instead of the Python module (`python -m eldendisk`), we need a dedicated reference document for the standalone version.

Create a new file named `cli-commands-exe.md` mirroring the existing **[cli-commands.md](../guilde/cli-commands.md)**, but updating the execution context.[cite: 7]

*   **Command Syntax:** Update `python -m eldendisk <command> [options]` to `eldendisk.exe <command> [options]`.[cite: 7]
*   **Commands:** Include all existing commands: `run`, `effects`, `animations`, and `hash`.[cite: 7]
*   **Flags & Options:** Document all flags (e.g., `--attach`, `--game-dir`, `--hz`) and their default behaviours.[cite: 7]
*   **Exit Codes:** Outline standard exit codes (`0` for success, `1` for error, `2` for profile/usage errors, `3` for EAC detection, `130` for user interrupt).[cite: 7]

### 4. Setup End-to-End (E2E) Development Run Pipeline

To ensure the Python source code and the compiled `.exe` work seamlessly together, we are introducing a standard End-to-End development pipeline script. Instead of manually running the Python module and then separately building and testing the `.exe`, developers will use a single unified cycle.

**Pipeline Script:** `tools/dev_pipeline.py`

**Execution Flow:**
1. **Pre-check:** Executes Python unit tests or a dry-run to validate the source code.
2. **Build:** Executes `python -m eldendisk build -c` to compile the standalone executable.
3. **Launch:** Executes `./dist/eldendisk.exe run -v`, which automatically launches the game and begins the telemetry process via the newly built executable.

**Usage:**
```commandline
python tools/dev_pipeline.py
```
This standardizes the development and testing cycle, guaranteeing that what works in the source code exactly matches the behavior of the final distributed executable.

---

## Requirements

### 1. Catch up with previous versions

_**Read previous documentation to understand what is going on in depth.**_

- **Changes:**
  - **[changes-version-1.2.1.md](changes-version-1.2.1.md)**
  - **[changes-version-1.3.0.md](changes-version-1.3.0.md)**
  - **[changes-version-1.4.0.md](changes-version-1.4.0.md)**
  - **[changes-version-1.4.1.md](changes-version-1.4.1.md)**
  - **[changes-version-1.4.2.md](changes-version-1.4.2.md)**
  - **[changes-version-1.5.0.md](changes-version-1.5.0.md)**
- **Specification:**
  - **[elden-telemetry-spec-v1.0.0.md](../specs/elden-telemetry-spec-v1.0.0.md)**
  - **[elden-telemetry-spec-v1.1.0.md](../specs/elden-telemetry-spec-v1.1.0.md)**
  - **[elden-telemetry-spec-v1.2.0.md](../specs/elden-telemetry-spec-v1.2.0.md)**
  - **[elden-disk-spec-v1.3.0.md](../specs/elden-disk-spec-v1.3.0.md)**
  - **[elden-disk-spec-v1.4.0.md](../specs/elden-disk-spec-v1.4.0.md)**
  - **[elden-disk-spec-v1.4.1.md](../specs/elden-disk-spec-v1.4.1.md)**
  - **[elden-disk-spec-v1.4.2.md](../specs/elden-disk-spec-v1.4.2.md)**
  - **[elden-disk-spec-v1.5.0.md](../specs/elden-disk-spec-v1.5.0.md)**
- **Implementation Plan:**
  - **[implementation_plan_v1.2.1.md](../implementations/implementation_plan_v1.2.1.md)**
  - **[implementation_plan_v1.3.0.md](../implementations/implementation_plan_v1.3.0.md)**
  - **[implementation_plan_v1.4.0.md](../implementations/implementation_plan_v1.4.0.md)**
  - **[implementation_plan_v1.4.1.md](../implementations/implementation_plan_v1.4.1.md)**
  - **[implementation_plan_v1.4.2.md](../implementations/implementation_plan_v1.4.2.md)**
  - **[implementation_plan_v1.5.0.md](../implementations/implementation_plan_v1.5.0.md)**

### 2. Documentation

_**Scan the whole project and every detail of the source code to draft perfectly new documentation.**_

- **New Specification Version `1.5.1`:**
  - Write **[NEW] elden-disk-spec-v1.5.1.md**
  - Save at `./docs/specs/elden-disk-spec-v1.5.1.md`
- **New Implementation Plan:**
  - Write **[NEW] implementation_plan_v1.5.1.md**.
  - Save at `./docs/implementations/implementation_plan_v1.5.1.md`
- **CLI Commands (.exe format):**
  - Write **[NEW] cli-commands-exe.md**
  - Save at `./docs/cli-commands-exe.md`

### 3. Integration (Take actions)
- Develop features according to **elden-disk-spec-v1.5.1.md** and **implementation_plan_v1.5.1.md**.
- Create **`tools/dev_pipeline.py`** to automate the build and run cycle.
- Verification via **Unit Tests** (Ensure the `.exe` builds successfully and runs independently).
- Update the **Tool-Version** and all documentation affected by these **Changes**.
# Open Build Service (OBS) KMP Packaging

This directory contains the packaging files to build official **openSUSE Kernel Module Packages (KMP)** on the [Open Build Service (OBS)](https://build.opensuse.org/).

---

## 💡 How KMP Packages Survive Kernel Updates

In openSUSE, kernel modules packaged via `%kernel_module_package` survive updates through two mechanisms:

1. **Weak-Updates (Immediate Compatibility):**
   When openSUSE installs a new kernel version via `zypper dup` or `zypper up`, the system rpm scriptlets execute `/usr/lib/module-init-tools/kernel-scriptlets/kmp-post`. If the new kernel's symbol checksums (kABI) are compatible with the driver, it creates symlinks in `/lib/modules/<new-kernel>/weak-updates/`. The driver continues working **immediately without requiring a recompile**.

2. **OBS Automatic Rebuilds (Recompilation on kABI Breaks):**
   Whenever a major kernel update is published in openSUSE (Tumbleweed, Slowroll, or Leap), OBS automatically detects the new `kernel-default-devel` package and rebuilds your package against the new kernel. `zypper dup` then pulls down the updated RPM seamlessly.

---

## 📦 Package Files

- **`hp-dragonfly-folio-camera.spec`**: The RPM spec file configuring `%kernel_module_package` for `kernel-default`, building the 4 kernel modules (`intel_skl_int3472_discrete`, `ov08a10`, `og0ve1b`, `leds-lm3643`), compiling `ir-grab`, and installing udev rules + Howdy plugins.
- **`preamble`**: Metadata defining runtime requirements and driver enhancement flags for the KMP subpackage.
- **`_service`**: Open Build Service source service file configuring OBS to automatically track this GitHub repository (`main` branch) and generate source archives on commit.

---

## 🚀 Setup Instructions

### Option A: Using the OBS Web UI (`build.opensuse.org`)

1. **Log in or Sign Up:**
   Visit [build.opensuse.org](https://build.opensuse.org/) and log in with your openSUSE account.

2. **Create a Package in your Home Project:**
   - Go to your home project (`home:<username>`).
   - Click **Add Package**.
   - Name: `hp-dragonfly-folio-camera`
   - Title: `HP Dragonfly Folio G3 Linux Camera & IR Drivers`
   - Save.

3. **Upload Packaging Files:**
   In your new package page, add the 3 files from this directory:
   - `_service`
   - `hp-dragonfly-folio-camera.spec`
   - `preamble`

4. **Add Repositories:**
   - Go to the **Repositories** tab in your home project (or package).
   - Click **Add from a Distribution** and select your distribution (e.g., `openSUSE Tumbleweed` or `openSUSE Slowroll`).
   - OBS will automatically trigger `obs_scm`, clone your GitHub repository, compile the KMP package, and publish the RPMs.

---

### Option B: Using the `osc` CLI Tool

1. **Install `osc`:**
   ```bash
   sudo zypper install -y osc
   ```

2. **Check out your home project:**
   ```bash
   osc checkout home:<your-username>
   cd home:<your-username>
   ```

3. **Create the package directory and copy files:**
   ```bash
   osc mkpac hp-dragonfly-folio-camera
   cd hp-dragonfly-folio-camera
   cp /path/to/hp-dragonfly-folio-linux-camera/packaging/obs/* .
   ```

4. **Commit and trigger build on OBS:**
   ```bash
   osc add *
   osc commit -m "Initial HP Dragonfly Folio camera KMP package"
   ```

---

## 📥 Adding Your Repository to Zypper

Once OBS finishes building (usually 2–3 minutes), add your personal repository to zypper:

```bash
# For openSUSE Tumbleweed:
sudo zypper addrepo -f https://download.opensuse.org/repositories/home:/<your-username>/openSUSE_Tumbleweed/ hp-camera

# Install the packages:
sudo zypper refresh
sudo zypper install hp-dragonfly-folio-camera hp-dragonfly-folio-camera-kmp-default
```

From this point forward, every `zypper dup` will automatically keep your camera drivers updated alongside your kernel!

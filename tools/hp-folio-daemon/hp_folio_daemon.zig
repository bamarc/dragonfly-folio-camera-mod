// HP Dragonfly Folio G3 - Folio Mode & Hinge Switch Daemon
// Written in Zig for high performance, zero runtime overhead, and minimal memory footprint.

const std = @import("std");
const math = std.math;
const fs = std.fs;
const c = @cImport({
    @cInclude("linux/uinput.h");
    @cInclude("linux/input.h");
    @cInclude("sys/ioctl.h");
    @cInclude("fcntl.h");
    @cInclude("unistd.h");
    @cInclude("signal.h");
    @cInclude("string.h");
});

const DEFAULT_SCALE: f64 = 0.0001;

pub const FolioMode = enum {
    Laptop,
    Stage,
    Tablet,
};

pub const FolioState = struct {
    mode: FolioMode,
    tablet_switch: i32,
    kbd_inhibit: bool,
    touchpad_inhibit: bool,
    normal_y: f64,
    normal_z: f64,
    total_angle: f64,
    qx: f64,
    qy: f64,
    qz: f64,
    qw: f64,
};

var global_uinput_fd: c_int = -1;
var global_kbd_path: ?[128]u8 = null;
var global_kbd_len: usize = 0;
var global_touchpad_path: ?[128]u8 = null;
var global_touchpad_len: usize = 0;
var global_running: bool = true;
var debug_logging: bool = false;
var enable_osd: bool = true;

fn sendOsdToBus(addr_arg: ?[]const u8, icon: []const u8, text: []const u8) void {
    var argv_buf: [10][]const u8 = undefined;
    var argv_len: usize = 0;

    argv_buf[argv_len] = "/usr/bin/busctl"; argv_len += 1;
    if (addr_arg) |addr| {
        argv_buf[argv_len] = addr; argv_len += 1;
    } else {
        argv_buf[argv_len] = "--user"; argv_len += 1;
    }
    argv_buf[argv_len] = "call"; argv_len += 1;
    argv_buf[argv_len] = "org.kde.plasmashell"; argv_len += 1;
    argv_buf[argv_len] = "/org/kde/osdService"; argv_len += 1;
    argv_buf[argv_len] = "org.kde.osdService"; argv_len += 1;
    argv_buf[argv_len] = "showText"; argv_len += 1;
    argv_buf[argv_len] = "ss"; argv_len += 1;
    argv_buf[argv_len] = icon; argv_len += 1;
    argv_buf[argv_len] = text; argv_len += 1;

    var child = std.process.Child.init(argv_buf[0..argv_len], std.heap.page_allocator);
    child.stdin_behavior = .Ignore;
    child.stdout_behavior = .Ignore;
    child.stderr_behavior = .Ignore;
    _ = child.spawn() catch return;
    _ = child.wait() catch return;
}

fn notifyKdeOsd(icon: []const u8, text: []const u8) void {
    if (!enable_osd) return;

    if (c.geteuid() == 0) {
        // System service running as root: iterate over /run/user/*/bus to notify active desktop sessions
        var dir = fs.openDirAbsolute("/run/user", .{ .iterate = true }) catch {
            sendOsdToBus(null, icon, text);
            return;
        };
        defer dir.close();

        var it = dir.iterate();
        var found_any = false;
        while (it.next() catch null) |entry| {
            if (entry.kind == .directory) {
                const uid = std.fmt.parseInt(u32, entry.name, 10) catch continue;
                if (uid == 0) continue;

                var bus_path_buf: [128]u8 = undefined;
                const bus_path = std.fmt.bufPrint(&bus_path_buf, "/run/user/{s}/bus", .{entry.name}) catch continue;
                if (fs.accessAbsolute(bus_path, .{})) |_| {
                    var addr_arg_buf: [160]u8 = undefined;
                    const addr_arg = std.fmt.bufPrint(&addr_arg_buf, "--address=unix:path={s}", .{bus_path}) catch continue;
                    sendOsdToBus(addr_arg, icon, text);
                    found_any = true;
                } else |_| {}
            }
        }
        if (!found_any) {
            sendOsdToBus(null, icon, text);
        }
    } else {
        // Running as regular user session
        sendOsdToBus(null, icon, text);
    }
}

fn handleSignal(_: c_int) callconv(.c) void {
    global_running = false;
}

fn setInhibited(path: []const u8, val: u8) void {
    const fd = fs.openFileAbsolute(path, .{ .mode = .write_only }) catch return;
    defer fd.close();
    const str = if (val == 1) "1\n" else "0\n";
    _ = fd.write(str) catch {};
}

fn restoreHardware() void {
    if (global_kbd_path) |p| {
        setInhibited(p[0..global_kbd_len], 0);
    }
    if (global_touchpad_path) |p| {
        setInhibited(p[0..global_touchpad_len], 0);
    }
    if (global_uinput_fd >= 0) {
        _ = c.ioctl(global_uinput_fd, c.UI_DEV_DESTROY);
        _ = c.close(global_uinput_fd);
        global_uinput_fd = -1;
    }
}

pub fn classify(qx: f64, qy: f64, qz: f64, qw: f64) FolioState {
    const abs_w = @abs(qw);
    const clamped_w = if (abs_w > 1.0) 1.0 else abs_w;
    const total_angle = 2.0 * math.acos(clamped_w) * (180.0 / math.pi);

    const normal_y = 2.0 * (qy * qz - qx * qw);
    const normal_z = 1.0 - 2.0 * (qx * qx + qy * qy);

    var mode = FolioMode.Laptop;
    var tablet_switch: i32 = 0;
    var kbd_inhibit: bool = false;
    var touchpad_inhibit: bool = false;

    // 1. Flat or Tilted Tablet Mode:
    // Screen is pulled forward and folded down flat over keyboard and touchpad.
    // Screen normal points directly UP (normal_z >= 0.85), normal_y is near zero (-0.15 <= normal_y <= 0.25),
    // and hinge twist qx is small (|qx| < 0.20).
    // This relies directly on the physical surface normal vector, which is completely invariant to sensor yaw flips.
    if (normal_z >= 0.85 and normal_y >= -0.15 and normal_y <= 0.25 and @abs(qx) < 0.20) {
        mode = .Tablet;
        tablet_switch = 1;
        kbd_inhibit = true;
        touchpad_inhibit = true;
    }
    // 2. Stage / Media Mode:
    // Screen pulled forward into magnetic notch above touchpad.
    // Normal faces forward (normal_y > 0.70) and tilted up (0.45 <= normal_z <= 0.65).
    else if (normal_y > 0.70 and normal_z >= 0.45 and normal_z <= 0.65) {
        mode = .Stage;
        tablet_switch = 1;
        kbd_inhibit = true;
        touchpad_inhibit = false; // Touchpad exposed!
    }
    // 3. Normal Laptop (Clamshell) Mode:
    // Screen hinged at the back. Covers upright view (normal_z < 0.45) AND
    // max tilted back (normal_y < 0.0, normal_z ~ 0.81).
    else {
        mode = .Laptop;
        tablet_switch = 0;
        kbd_inhibit = false;
        touchpad_inhibit = false;
    }

    return .{
        .mode = mode,
        .tablet_switch = tablet_switch,
        .kbd_inhibit = kbd_inhibit,
        .touchpad_inhibit = touchpad_inhibit,
        .normal_y = normal_y,
        .normal_z = normal_z,
        .total_angle = total_angle,
        .qx = qx,
        .qy = qy,
        .qz = qz,
        .qw = qw,
    };
}

fn findQuatPath(buf: *[128]u8) ?[]const u8 {
    // Check known iio:device9 first
    const primary = "/sys/bus/iio/devices/iio:device9/in_rot_quaternion_raw";
    if (fs.accessAbsolute(primary, .{})) |_| {
        @memcpy(buf[0..primary.len], primary);
        return buf[0..primary.len];
    } else |_| {}

    // Search iio:device* for relative_orientation
    var dir = fs.openDirAbsolute("/sys/bus/iio/devices", .{ .iterate = true }) catch return null;
    defer dir.close();
    var it = dir.iterate();
    while (it.next() catch null) |entry| {
        if (entry.kind == .directory or entry.kind == .sym_link) {
            if (std.mem.startsWith(u8, entry.name, "iio:device")) {
                var name_buf: [64]u8 = undefined;
                const dev_name_path = std.fmt.bufPrint(&name_buf, "/sys/bus/iio/devices/{s}/name", .{entry.name}) catch continue;
                var nfile = fs.openFileAbsolute(dev_name_path, .{}) catch continue;
                defer nfile.close();
                var nbytes: [64]u8 = undefined;
                const r = nfile.read(&nbytes) catch continue;
                const dname = std.mem.trim(u8, nbytes[0..r], " \r\n");
                if (std.mem.eql(u8, dname, "relative_orientation")) {
                    const quat_path = std.fmt.bufPrint(buf, "/sys/bus/iio/devices/{s}/in_rot_quaternion_raw", .{entry.name}) catch continue;
                    return quat_path;
                }
            }
        }
    }
    return null;
}

fn discoverInputDevices() void {
    var dir = fs.openDirAbsolute("/sys/class/input", .{ .iterate = true }) catch return;
    defer dir.close();
    var it = dir.iterate();
    while (it.next() catch null) |entry| {
        if (std.mem.startsWith(u8, entry.name, "input")) {
            var npath_buf: [128]u8 = undefined;
            const npath = std.fmt.bufPrint(&npath_buf, "/sys/class/input/{s}/name", .{entry.name}) catch continue;
            var nfile = fs.openFileAbsolute(npath, .{}) catch continue;
            defer nfile.close();
            var nbytes: [128]u8 = undefined;
            const r = nfile.read(&nbytes) catch continue;
            const dname = std.mem.trim(u8, nbytes[0..r], " \r\n");

            var ipath_buf: [128]u8 = undefined;
            const ipath = std.fmt.bufPrint(&ipath_buf, "/sys/class/input/{s}/inhibited", .{entry.name}) catch continue;

            if (fs.accessAbsolute(ipath, .{})) |_| {
                if (std.mem.indexOf(u8, dname, "keyboard") != null or std.mem.indexOf(u8, dname, "Keyboard") != null) {
                    var kbuf: [128]u8 = undefined;
                    @memcpy(kbuf[0..ipath.len], ipath);
                    global_kbd_path = kbuf;
                    global_kbd_len = ipath.len;
                    if (debug_logging) std.debug.print("[HP Folio] Discovered keyboard inhibit: {s} ({s})\n", .{ ipath, dname });
                } else if (std.mem.indexOf(u8, dname, "Touchpad") != null or std.mem.indexOf(u8, dname, "SYNA30F4") != null) {
                    var tbuf: [128]u8 = undefined;
                    @memcpy(tbuf[0..ipath.len], ipath);
                    global_touchpad_path = tbuf;
                    global_touchpad_len = ipath.len;
                    if (debug_logging) std.debug.print("[HP Folio] Discovered touchpad inhibit: {s} ({s})\n", .{ ipath, dname });
                }
            } else |_| {}
        }
    }
}

fn createUinputDevice() !c_int {
    const fd = c.open("/dev/uinput", c.O_WRONLY | c.O_NONBLOCK);
    if (fd < 0) {
        return error.OpenFailed;
    }

    if (c.ioctl(fd, c.UI_SET_EVBIT, c.EV_SW) < 0) {
        _ = c.close(fd);
        return error.IoctlFailed;
    }
    if (c.ioctl(fd, c.UI_SET_SWBIT, c.SW_TABLET_MODE) < 0) {
        _ = c.close(fd);
        return error.IoctlFailed;
    }

    var usetup: c.struct_uinput_setup = std.mem.zeroes(c.struct_uinput_setup);
    usetup.id.bustype = c.BUS_HOST;
    usetup.id.vendor = 0x103c;
    usetup.id.product = 0x8a05;
    usetup.id.version = 1;
    const name = "HP Folio Mode Switch Device";
    @memcpy(usetup.name[0..name.len], name);

    if (c.ioctl(fd, c.UI_DEV_SETUP, &usetup) < 0) {
        _ = c.close(fd);
        return error.SetupFailed;
    }
    if (c.ioctl(fd, c.UI_DEV_CREATE) < 0) {
        _ = c.close(fd);
        return error.CreateFailed;
    }

    return fd;
}

fn emitSwitch(fd: c_int, state: i32) void {
    var ev: [2]c.struct_input_event = undefined;
    ev[0] = std.mem.zeroes(c.struct_input_event);
    ev[0].type = c.EV_SW;
    ev[0].code = c.SW_TABLET_MODE;
    ev[0].value = state;

    ev[1] = std.mem.zeroes(c.struct_input_event);
    ev[1].type = c.EV_SYN;
    ev[1].code = c.SYN_REPORT;
    ev[1].value = 0;

    _ = c.write(fd, &ev, @sizeOf(@TypeOf(ev)));
}

pub fn readSample(quat_path: []const u8) ?FolioState {
    var file = fs.openFileAbsolute(quat_path, .{}) catch return null;
    defer file.close();

    var buf: [128]u8 = undefined;
    const bytes_read = file.read(&buf) catch return null;
    const str = std.mem.trim(u8, buf[0..bytes_read], " \t\r\n");

    var iter = std.mem.tokenizeAny(u8, str, " \t");
    var raw: [4]f64 = undefined;
    var i: usize = 0;
    while (iter.next()) |token| : (i += 1) {
        if (i >= 4) break;
        const val = std.fmt.parseInt(i64, token, 10) catch return null;
        raw[i] = @as(f64, @floatFromInt(val)) * DEFAULT_SCALE;
    }
    if (i < 4) return null;

    const norm = math.sqrt(raw[0]*raw[0] + raw[1]*raw[1] + raw[2]*raw[2] + raw[3]*raw[3]);
    if (norm == 0.0) return null;

    return classify(raw[0] / norm, raw[1] / norm, raw[2] / norm, raw[3] / norm);
}

pub fn main() !void {
    const args = std.os.argv;
    var once_mode = false;

    for (args[1..]) |arg| {
        const s = std.mem.span(arg);
        if (std.mem.eql(u8, s, "--debug") or std.mem.eql(u8, s, "-d")) {
            debug_logging = true;
        } else if (std.mem.eql(u8, s, "--status") or std.mem.eql(u8, s, "-s")) {
            once_mode = true;
        } else if (std.mem.eql(u8, s, "--help") or std.mem.eql(u8, s, "-h")) {
            std.debug.print(
                \\HP Dragonfly Folio G3 Hinge & Mode Switch Daemon (Zig)
                \\Usage: hp_folio_daemon [OPTIONS]
                \\
                \\Options:
                \\  -s, --status   Print current Folio hardware mode and exit
                \\  -d, --debug    Enable verbose console logging
                \\  -h, --help     Show this help message
                \\
            , .{});
            return;
        }
    }

    var qpath_buf: [128]u8 = undefined;
    const quat_path = findQuatPath(&qpath_buf) orelse {
        std.debug.print("[HP Folio] Error: Relative orientation sensor not found in sysfs!\n", .{});
        return error.SensorNotFound;
    };

    if (once_mode) {
        if (readSample(quat_path)) |sample| {
            std.debug.print("Folio Mode: {s}\n", .{@tagName(sample.mode)});
            std.debug.print("  SW_TABLET_MODE : {d}\n", .{sample.tablet_switch});
            std.debug.print("  Kbd Inhibit    : {s}\n", .{if (sample.kbd_inhibit) "YES" else "NO"});
            std.debug.print("  Pad Inhibit    : {s}\n", .{if (sample.touchpad_inhibit) "YES" else "NO"});
            std.debug.print("  Screen Normal  : [Y={d:.3}, Z={d:.3}]\n", .{ sample.normal_y, sample.normal_z });
            std.debug.print("  Total 3D Angle : {d:.1}°\n", .{sample.total_angle});
            std.debug.print("  Quaternion     : [{d:.4}, {d:.4}, {d:.4}, {d:.4}]\n", .{ sample.qx, sample.qy, sample.qz, sample.qw });
        } else {
            std.debug.print("[HP Folio] Error reading sample.\n", .{});
        }
        return;
    }

    // Set up signal handlers for graceful exit
    _ = c.signal(c.SIGINT, handleSignal);
    _ = c.signal(c.SIGTERM, handleSignal);
    _ = c.signal(c.SIGHUP, handleSignal);

    discoverInputDevices();

    // Create uinput device
    global_uinput_fd = createUinputDevice() catch |err| {
        std.debug.print("[HP Folio] Failed to create /dev/uinput device ({s}). Ensure write permissions.\n", .{@errorName(err)});
        return err;
    };
    defer restoreHardware();

    std.debug.print("[HP Folio] Started Zig Folio Switch Daemon successfully.\n", .{});

    var current_mode = FolioMode.Laptop;
    var candidate_mode = current_mode;
    var candidate_count: usize = 0;
    var debug_tick: usize = 0;
    const HYSTERESIS_SAMPLES: usize = 2; // Require 2 consecutive matching samples (200ms)

    // Initial state emission
    if (readSample(quat_path)) |initial_sample| {
        current_mode = initial_sample.mode;
        candidate_mode = current_mode;
        emitSwitch(global_uinput_fd, initial_sample.tablet_switch);
        if (global_kbd_path) |p| setInhibited(p[0..global_kbd_len], if (initial_sample.kbd_inhibit) 1 else 0);
        if (global_touchpad_path) |p| setInhibited(p[0..global_touchpad_len], if (initial_sample.touchpad_inhibit) 1 else 0);
        std.debug.print("[HP Folio] Initialized in {s} Mode (SW_TABLET_MODE={d})\n", .{ @tagName(current_mode), initial_sample.tablet_switch });
    }

    // Main loop (10 Hz = 100ms)
    while (global_running) {
        _ = c.usleep(100_000);

        if (readSample(quat_path)) |sample| {
            if (debug_logging) {
                debug_tick += 1;
                if (debug_tick >= 5) {
                    debug_tick = 0;
                    std.debug.print("[DEBUG] Current={s} SampleMode={s} Angle={d:.1}° Normal=[Y={d:.2}, Z={d:.2}] qx={d:.3}\n",
                        .{ @tagName(current_mode), @tagName(sample.mode), sample.total_angle, sample.normal_y, sample.normal_z, sample.qx });
                }
            }

            if (sample.mode != current_mode) {
                if (sample.mode == candidate_mode) {
                    candidate_count += 1;
                    if (candidate_count >= HYSTERESIS_SAMPLES) {
                        current_mode = sample.mode;
                        candidate_count = 0;

                        // Emit switch to Linux kernel
                        emitSwitch(global_uinput_fd, sample.tablet_switch);

                        // Mute/Unmute hardware
                        if (global_kbd_path) |p| {
                            setInhibited(p[0..global_kbd_len], if (sample.kbd_inhibit) 1 else 0);
                        }
                        if (global_touchpad_path) |p| {
                            setInhibited(p[0..global_touchpad_len], if (sample.touchpad_inhibit) 1 else 0);
                        }

                        std.debug.print("[HP Folio] >>> Switched to {s} Mode <<< (SW_TABLET_MODE={d})\n", .{ @tagName(current_mode), sample.tablet_switch });

                        switch (current_mode) {
                            .Laptop => notifyKdeOsd("computer", "Laptop Mode — Keyboard Enabled"),
                            .Stage => notifyKdeOsd("input-tablet", "Stage Mode — Keyboard Disabled"),
                            .Tablet => notifyKdeOsd("input-tablet", "Tablet Mode — Auto-Rotation Active"),
                        }
                    }
                } else {
                    candidate_mode = sample.mode;
                    candidate_count = 1;
                }
            } else {
                candidate_count = 0;
            }
        }
    }

    std.debug.print("[HP Folio] Shutting down, restoring hardware input.\n", .{});
    restoreHardware();
}

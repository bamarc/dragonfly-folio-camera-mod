#!/usr/bin/env python3
# hp_presence_daemon.py - Human Presence Detection, Walk-Away Auto-Lock & Wake on Approach
# for HP Dragonfly Folio 13.5" G3 on KDE Plasma (Wayland/X11).
#
# Interfaces with the STMicroelectronics VL53L5 ToF & Biometric Presence Sensor over Intel ISH.
# Provides a native KDE Plasma System Tray StatusNotifierItem applet with click toggle.

import configparser
import glob
import os
import select
import signal
import struct
import sys
import time

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"
STATUS_AWAY = "away"


class HpPresenceDaemon(dbus.service.Object):
	"""
	Background presence daemon and KDE StatusNotifierItem tray applet.
	"""

	def __init__(self, bus):
		self.bus = bus
		self.config_dir = os.path.expanduser("~/.config/hp-presence")
		self.config_file = os.path.join(self.config_dir, "config.ini")
		self._load_config()

		# State
		self.enabled = self.config.getboolean("presence", "enabled", fallback=True)
		self.away_timeout = self.config.getfloat("presence", "away_timeout_sec", fallback=10.0)
		self.approach_dist_cm = self.config.getfloat("presence", "approach_distance_cm", fallback=80.0)
		self.max_dist_cm = self.config.getfloat("presence", "max_distance_cm", fallback=110.0)
		self.enable_tray = self.config.getboolean("presence", "enable_tray", fallback=True)

		self.paused_until = 0.0
		self.is_locked = False
		self.is_present = False
		self.current_distance_cm = 0.0
		self.confidence = 0
		self.away_since = None
		self.wake_attempted = False
		self.sensor_fd = None
		self.sensor_dev = None

		# Connect to KDE / FreeDesktop ScreenSaver
		self._setup_screensaver()

		# Locate & open sensor
		self._open_sensor()

		# Initialize D-Bus service and Tray Item
		self.dbus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
		dbus.service.Object.__init__(self, self.bus, "/StatusNotifierItem")
		self._setup_menu()

		if self.enable_tray:
			self._register_tray()

		# Add periodic timer for presence polling and state machine
		GLib.timeout_add(150, self._poll_presence)

	def _load_config(self):
		self.config = configparser.ConfigParser()
		if os.path.exists(self.config_file):
			self.config.read(self.config_file)
		else:
			os.makedirs(self.config_dir, exist_ok=True)
			self.config["presence"] = {
				"enabled": "true",
				"away_timeout_sec": "10.0",
				"approach_distance_cm": "80.0",
				"max_distance_cm": "110.0",
				"enable_tray": "true"
			}
			with open(self.config_file, "w") as f:
				self.config.write(f)

	def _setup_screensaver(self):
		try:
			self.ss_obj = self.bus.get_object("org.freedesktop.ScreenSaver", "/ScreenSaver")
			self.ss_iface = dbus.Interface(self.ss_obj, "org.freedesktop.ScreenSaver")
			self.is_locked = bool(self.ss_iface.GetActive())
			self.bus.add_signal_receiver(
				self._on_lock_changed,
				signal_name="ActiveChanged",
				dbus_interface="org.freedesktop.ScreenSaver",
				path="/ScreenSaver"
			)
		except Exception as e:
			print(f"[HP Presence] Warning: ScreenSaver D-Bus interface unavailable: {e}", file=sys.stderr)
			self.ss_iface = None

	def _on_lock_changed(self, active):
		self.is_locked = bool(active)
		print(f"[HP Presence] Lock state changed: locked={self.is_locked}")
		if not self.is_locked:
			self.away_since = None
			self.wake_attempted = False
		self._update_tray()

	def _open_sensor(self):
		# First check symlink /dev/hp-presence
		candidate = "/dev/hp-presence"
		if not os.path.exists(candidate):
			# Search dynamically for Biometric Presence Sensor
			for dev_dir in glob.glob("/sys/bus/platform/devices/HID-SENSOR-2000e1.*"):
				real = os.path.realpath(dev_dir)
				name_file = os.path.join(real, "feature-a-200301", "feature-a-200301-value")
				if os.path.exists(name_file):
					try:
						with open(name_file) as f:
							txt = "".join(chr(int(x)) for x in f.read().split() if x.isdigit() and 32 <= int(x) < 127)
						if "Biometric Presence Sensor" in txt:
							# enable sensor
							ef = os.path.join(real, "enable_sensor")
							if os.path.exists(ef):
								try:
									with open(ef, "w") as out:
										out.write("1\n")
								except Exception:
									pass
							hdir = os.path.join(real, "..", "hidraw")
							if os.path.exists(hdir):
								for h in os.listdir(hdir):
									if h.startswith("hidraw"):
										candidate = os.path.join("/dev", h)
										break
							break
					except Exception:
						pass

		if os.path.exists(candidate):
			try:
				self.sensor_fd = os.open(candidate, os.O_RDWR | os.O_NONBLOCK)
				self.sensor_dev = candidate
				print(f"[HP Presence] Successfully opened presence sensor at {candidate}")
			except Exception as e:
				print(f"[HP Presence] Error opening {candidate}: {e}", file=sys.stderr)
		else:
			print("[HP Presence] Presence sensor device node not found.", file=sys.stderr)

	def _poll_presence(self):
		if self.sensor_fd is None:
			self._open_sensor()
			return True

		# Read latest packet
		try:
			while True:
				r, _, _ = select.select([self.sensor_fd], [], [], 0)
				if not r:
					break
				data = os.read(self.sensor_fd, 256)
				if len(data) >= 33 and data[0] == 4:
					self.current_distance_cm = struct.unpack("<I", data[27:31])[0] / 10.0
					self.is_present = bool(data[31])
					self.confidence = data[32]
		except Exception:
			pass

		now = time.time()
		is_paused = (not self.enabled) or (now < self.paused_until)

		# State Machine
		if not is_paused:
			if not self.is_locked:
				# Check if user walked away
				if (not self.is_present) or (self.current_distance_cm > self.max_dist_cm):
					if self.away_since is None:
						self.away_since = now
					elif now - self.away_since >= self.away_timeout:
						print(f"[HP Presence] User absent for {self.away_timeout}s -> Locking session.")
						self._lock_session()
						self.away_since = None
				else:
					self.away_since = None
			else:
				# Session is locked: Check if user has approached to wake up
				if self.is_present and (self.current_distance_cm <= self.approach_dist_cm):
					if not self.wake_attempted:
						print(f"[HP Presence] User approached ({self.current_distance_cm:.1f} cm) -> Waking display for Howdy.")
						self._wake_session()
						self.wake_attempted = True
					self.away_since = None
				else:
					# Stepped away while locked; reset latch so next approach triggers wake
					self.wake_attempted = False

		self._update_tray()
		return True

	def _lock_session(self):
		if self.ss_iface:
			try:
				self.ss_iface.Lock()
				return
			except Exception:
				pass
		os.system("loginctl lock-session")

	def _wake_session(self):
		if self.ss_iface:
			try:
				self.ss_iface.SimulateUserActivity()
				return
			except Exception:
				pass
		os.system("loginctl activate-session 2>/dev/null")

	def toggle(self):
		self.enabled = not self.enabled
		self.paused_until = 0.0
		state_str = "ENABLED" if self.enabled else "PAUSED"
		print(f"[HP Presence] User toggled presence auto-lock: {state_str}")
		self._update_tray()

	def pause_for(self, minutes):
		self.enabled = True
		self.paused_until = time.time() + (minutes * 60)
		print(f"[HP Presence] Paused for {minutes} minutes")
		self._update_tray()

	def resume(self):
		self.enabled = True
		self.paused_until = 0.0
		print("[HP Presence] Resumed active monitoring")
		self._update_tray()

	# --- StatusNotifierItem Protocol (KDE Plasma Tray) ---

	def _register_tray(self):
		try:
			self.bus_name = dbus.service.BusName(self.dbus_name, self.bus)
			watcher_obj = self.bus.get_object("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher")
			watcher = dbus.Interface(watcher_obj, "org.kde.StatusNotifierWatcher")
			watcher.RegisterStatusNotifierItem(self.dbus_name)
			print(f"[HP Presence] Registered KDE StatusNotifierItem: {self.dbus_name}")
		except Exception as e:
			print(f"[HP Presence] Could not register tray item with KDE watcher: {e}", file=sys.stderr)

	def _get_status_icon(self):
		now = time.time()
		if not self.enabled or now < self.paused_until:
			return "user-offline"
		if not self.is_present or (self.current_distance_cm > self.max_dist_cm):
			return "user-away"
		return "user-available"

	def _get_tooltip(self):
		now = time.time()
		if not self.enabled:
			status = "Disabled (Click to Enable)"
		elif now < self.paused_until:
			remaining = int((self.paused_until - now) / 60) + 1
			status = f"Paused ({remaining}m left)"
		elif not self.is_present:
			status = f"Away ({self.away_timeout:.0f}s auto-lock)"
		else:
			status = f"Present ({self.current_distance_cm:.1f} cm)"

		lock_status = "Locked" if self.is_locked else "Unlocked"
		return "HP Presence & Walk-Away Lock", f"Status: {status} | Screen: {lock_status}"

	def _update_tray(self):
		if not self.enable_tray:
			return
		self.NewIcon()
		self.NewToolTip()
		props = self.GetAll("org.kde.StatusNotifierItem")
		self.PropertiesChanged("org.kde.StatusNotifierItem", {
			"IconName": props["IconName"],
			"ToolTip": props["ToolTip"],
			"Status": props["Status"]
		}, [])

	@dbus.service.signal("org.freedesktop.DBus.Properties", signature="sa{sv}as")
	def PropertiesChanged(self, interface_name, changed_properties, invalidated_properties):
		pass

	@dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
	def Get(self, interface_name, property_name):
		return self.GetAll(interface_name).get(property_name, "")

	@dbus.service.method("org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}")
	def GetAll(self, interface_name):
		if interface_name not in ("org.kde.StatusNotifierItem", "org.freedesktop.StatusNotifierItem"):
			return {}

		title, body = self._get_tooltip()
		icon = self._get_status_icon()

		return {
			"Category": dbus.String("Hardware"),
			"Id": dbus.String("hp-presence"),
			"Title": dbus.String("HP Presence"),
			"Status": dbus.String("Active"),
			"IconName": dbus.String(icon),
			"IconThemePath": dbus.String(""),
			"OverlayIconName": dbus.String(""),
			"AttentionIconName": dbus.String(""),
			"AttentionMovieName": dbus.String(""),
			"ItemIsMenu": dbus.Boolean(False),
			"WindowId": dbus.Int32(0),
			"IconPixmap": dbus.Array([], signature="(iiiay)"),
			"OverlayIconPixmap": dbus.Array([], signature="(iiiay)"),
			"AttentionIconPixmap": dbus.Array([], signature="(iiiay)"),
			"Menu": dbus.ObjectPath("/MenuBar"),
			"ToolTip": dbus.Struct((
				dbus.String(icon),
				dbus.Array([], signature="(iiiay)"),
				dbus.String(title),
				dbus.String(body)
			), signature="sa(iiay)ss")
		}

	@dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ssv")
	def Set(self, interface_name, property_name, value):
		pass

	@dbus.service.signal("org.kde.StatusNotifierItem")
	def NewIcon(self):
		pass

	@dbus.service.signal("org.kde.StatusNotifierItem")
	def NewToolTip(self):
		pass

	@dbus.service.signal("org.kde.StatusNotifierItem")
	def NewStatus(self, status):
		pass

	@dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii")
	def Activate(self, x, y):
		"""Left click on tray icon toggles Walk-Away Lock."""
		self.toggle()

	@dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii")
	def ContextMenu(self, x, y):
		"""Right click on tray icon cycles modes or shows menu."""
		self.toggle()

	@dbus.service.method("org.kde.StatusNotifierItem", out_signature="s")
	def Category(self):
		return "Hardware"

	@dbus.service.method("org.kde.StatusNotifierItem", out_signature="s")
	def Id(self):
		return "hp-presence"

	@dbus.service.method("org.kde.StatusNotifierItem", out_signature="s")
	def Title(self):
		return "HP Presence"

	@dbus.service.method("org.kde.StatusNotifierItem", out_signature="s")
	def Status(self):
		return "Active"

	@dbus.service.method("org.kde.StatusNotifierItem", out_signature="s")
	def IconName(self):
		return self._get_status_icon()

	@dbus.service.method("org.kde.StatusNotifierItem", out_signature="(sa(iiay)ss)")
	def ToolTip(self):
		title, body = self._get_tooltip()
		return (self._get_status_icon(), [], title, body)

	@dbus.service.method("org.kde.StatusNotifierItem", out_signature="o")
	def Menu(self):
		return "/MenuBar"

	# --- DBusMenu Implementation (/MenuBar) ---

	def _setup_menu(self):
		self.menu_obj = MenuObject(self.bus, "/MenuBar", self)


class MenuObject(dbus.service.Object):
	"""Simple D-Bus Menu implementation for the tray context menu."""

	def __init__(self, bus, path, daemon):
		super().__init__(bus, path)
		self.daemon = daemon

	@dbus.service.method("com.canonical.dbusmenu", in_signature="iias", out_signature="u(ia{sv}av)")
	def GetLayout(self, parent_id, recursion_depth, property_names):
		now = time.time()
		is_active = self.daemon.enabled and (now >= self.daemon.paused_until)

		toggle_label = "Disable Walk-Away Lock" if is_active else "Enable Walk-Away Lock"
		status_label = f"Distance: {self.daemon.current_distance_cm:.1f} cm"

		def make_item(item_id, props, children=None):
			if children is None:
				children = []
			dbus_props = {}
			for k, v in props.items():
				if isinstance(v, bool):
					dbus_props[dbus.String(k)] = dbus.Boolean(v)
				elif isinstance(v, int):
					dbus_props[dbus.String(k)] = dbus.Int32(v)
				else:
					dbus_props[dbus.String(k)] = dbus.String(str(v))
			dbus_children = dbus.Array([make_item(*c) for c in children], signature="v")
			return dbus.Struct((dbus.Int32(item_id), dbus.Dictionary(dbus_props, signature="sv"), dbus_children), signature="ia{sv}av")

		items_spec = [
			(1, {"label": toggle_label, "type": "standard"}, []),
			(2, {"type": "separator"}, []),
			(3, {"label": "Pause for 30 minutes", "type": "standard"}, []),
			(4, {"label": "Pause for 1 hour", "type": "standard"}, []),
			(5, {"label": "Resume Monitoring", "type": "standard"}, []),
			(6, {"type": "separator"}, []),
			(7, {"label": status_label, "enabled": False}, []),
			(8, {"label": "Quit", "type": "standard"}, [])
		]

		root_children = dbus.Array([
			dbus.Struct(make_item(*spec), signature="(ia{sv}av)")
			for spec in items_spec
		], signature="v")

		root = dbus.Struct((
			dbus.Int32(0),
			dbus.Dictionary({dbus.String("children-display"): dbus.String("submenu")}, signature="sv"),
			root_children
		), signature="ia{sv}av")

		return (dbus.UInt32(1), root)

	@dbus.service.method("com.canonical.dbusmenu", in_signature="i", out_signature="b")
	def AboutToShow(self, item_id):
		return False

	@dbus.service.method("com.canonical.dbusmenu", in_signature="ai", out_signature="aiai")
	def AboutToShowGroup(self, item_ids):
		return (dbus.Array([], signature="i"), dbus.Array([], signature="i"))

	@dbus.service.method("com.canonical.dbusmenu", in_signature="aias", out_signature="a(ia{sv})")
	def GetGroupProperties(self, ids, property_names):
		return dbus.Array([], signature="(ia{sv})")

	@dbus.service.method("com.canonical.dbusmenu", in_signature="isvu")
	def Event(self, item_id, event_id, data, timestamp):
		if event_id == "clicked":
			if item_id == 1:
				self.daemon.toggle()
			elif item_id == 3:
				self.daemon.pause_for(30)
			elif item_id == 4:
				self.daemon.pause_for(60)
			elif item_id == 5:
				self.daemon.resume()
			elif item_id == 8:
				print("[HP Presence] User selected Quit from tray.")
				sys.exit(0)


def main():
	dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
	bus = dbus.SessionBus()

	daemon = HpPresenceDaemon(bus)
	loop = GLib.MainLoop()

	def handle_signal(sig, frame):
		print("\n[HP Presence] Shutting down...")
		loop.quit()

	signal.signal(signal.SIGINT, handle_signal)
	signal.signal(signal.SIGTERM, handle_signal)

	try:
		loop.run()
	finally:
		if daemon.sensor_fd is not None:
			os.close(daemon.sensor_fd)


if __name__ == "__main__":
	main()

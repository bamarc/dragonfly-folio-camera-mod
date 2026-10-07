#
# spec file for package hp-presence
#
# Copyright (c) 2026 SUSE LLC
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via https://bugs.opensuse.org/
#

Name:           hp-presence
Version:        0.1.0
Release:        0
Summary:        Human presence detection and walk-away auto-lock daemon for HP Dragonfly Folio G3
License:        GPL-2.0-only
Group:          System/GUI/KDE
URL:            https://github.com/bamarc/dragonfly-folio-camera-mod
BuildArch:      noarch
BuildRequires:  pkgconfig(udev)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  zstd
Requires:       python3
Requires:       python3-gobject
Requires:       python3-dbus-python
Requires:       udev
Requires:       systemd
Recommends:     howdy

%description
HP Dragonfly Folio 13.5" G3 human presence detection, walk-away auto-lock, and
approach auto-wake background service. Interacts with the Intel ISH ST VL53L5
Time-of-Flight (ToF) and Biometric Presence sensors, integrates with KDE Plasma
Wayland via StatusNotifierItem (system tray), and triggers screen lock / display
wake automatically.

%prep
%setup -q -c -T -D
if [ -f "%{_sourcedir}/%{name}-%{version}.tar.zst" ]; then
    tar -xf "%{_sourcedir}/%{name}-%{version}.tar.zst" --strip-components=1
elif ls %{_sourcedir}/%{name}*.tar.* 1>/dev/null 2>&1; then
    tar -xf $(ls %{_sourcedir}/%{name}*.tar.* | head -n 1) --strip-components=1
elif [ -d "%{_sourcedir}/tools" ]; then
    cp -a %{_sourcedir}/{tools,udev,LICENSE,README.md} .
fi

%build
# Pure python / systemd package, no compilation required

%install
# Install daemon executable
install -D -m 0755 tools/hp-presence/hp_presence_daemon.py %{buildroot}%{_libexecdir}/hp-presence/hp_presence_daemon.py

# Install systemd user service and preset
install -D -m 0644 tools/hp-presence/hp-presence.service %{buildroot}%{_userunitdir}/hp-presence.service
install -D -m 0644 tools/hp-presence/90-hp-presence.preset %{buildroot}%{_userpresetdir}/90-hp-presence.preset

# Install udev rule for sensor permissions
install -D -m 0644 udev/99-hp-presence.rules %{buildroot}%{_udevrulesdir}/99-hp-presence.rules

# Install default config file
install -D -m 0644 tools/hp-presence/config.ini.example %{buildroot}%{_sysconfdir}/hp-presence/config.ini

# Install desktop application / autostart file
install -D -m 0644 tools/hp-presence/hp-presence.desktop %{buildroot}%{_datadir}/applications/hp-presence.desktop

%post
%udev_rules_update
%systemd_user_post hp-presence.service

%preun
%systemd_user_preun hp-presence.service

%postun
%udev_rules_update
%systemd_user_postun_with_restart hp-presence.service

%files
%license LICENSE
%doc README.md
%dir %{_libexecdir}/hp-presence
%{_libexecdir}/hp-presence/hp_presence_daemon.py
%{_userunitdir}/hp-presence.service
%{_userpresetdir}/90-hp-presence.preset
%{_udevrulesdir}/99-hp-presence.rules
%dir %{_sysconfdir}/hp-presence
%config(noreplace) %{_sysconfdir}/hp-presence/config.ini
%{_datadir}/applications/hp-presence.desktop

%changelog

#
# spec file for package hp-folio-daemon
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

Name:           hp-folio-daemon
Version:        0.1.1
Release:        0
Summary:        Hinge and display mode switch daemon for HP Dragonfly Folio 13.5" G3
License:        GPL-2.0-only
Group:          System/Daemons
URL:            https://github.com/bamarc/dragonfly-folio-camera-mod
ExclusiveArch:  x86_64
BuildRequires:  pkgconfig(systemd)
BuildRequires:  pkgconfig(udev)
BuildRequires:  zig
BuildRequires:  zstd
Requires:       systemd
Requires:       udev

%description
HP Dragonfly Folio 13.5" G3 hinge and display mode switch daemon written in Zig.
Monitors the relative orientation quaternion sensor (iio:device9) to detect
transitions between Laptop (Clamshell), Stage (pull-forward media notch), and
Flat Tablet modes.

Emits Linux SW_TABLET_MODE input events via uinput for native KDE Plasma 6
and Wayland touch / virtual-keyboard adaptations, dynamically inhibits covered
keyboard and touchpad hardware in sysfs to prevent ghost touches, and triggers
native KDE OSD bezel notifications on mode transitions.

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
cd tools/hp-folio-daemon
zig build-exe hp_folio_daemon.zig -lc -O ReleaseSmall -fstrip -femit-bin=hp-folio-daemon

%install
# Install daemon executable (37 KB compiled Zig binary)
install -D -m 0755 tools/hp-folio-daemon/hp-folio-daemon %{buildroot}%{_libexecdir}/hp-folio-daemon

# Install systemd service
install -D -m 0644 tools/hp-folio-daemon/hp-folio-daemon.service %{buildroot}%{_unitdir}/hp-folio-daemon.service

%pre
%service_add_pre hp-folio-daemon.service

%post
%service_add_post hp-folio-daemon.service

%preun
%service_del_preun hp-folio-daemon.service

%postun
%service_del_postun hp-folio-daemon.service

%files
%license LICENSE
%doc README.md
%{_libexecdir}/hp-folio-daemon
%{_unitdir}/hp-folio-daemon.service

%changelog

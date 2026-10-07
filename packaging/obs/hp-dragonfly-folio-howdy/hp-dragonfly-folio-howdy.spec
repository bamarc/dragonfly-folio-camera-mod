#
# spec file for package hp-dragonfly-folio-howdy
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

Name:           hp-dragonfly-folio-howdy
Version:        0.1.0
Release:        0
Summary:        Howdy facial authentication integration and 3D ToF anti-spoofing for HP Dragonfly Folio G3
License:        GPL-2.0-only
Group:          Hardware/Camera
URL:            https://github.com/bamarc/dragonfly-folio-camera-mod
ExclusiveArch:  x86_64
BuildRequires:  gcc-c++
BuildRequires:  libcamera-devel
BuildRequires:  meson
BuildRequires:  ninja
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(udev)
BuildRequires:  zstd
Requires:       python3
Requires:       python3-numpy
Requires:       udev
Recommends:     howdy
Recommends:     hp-dragonfly-folio-camera-kmp
Recommends:     hp-presence

%description
Hardware integration utilities and Howdy recorder modules for the HP Dragonfly
Folio 13.5" G3 IR camera and Time-of-Flight (ToF) sensor.

Includes:
- ir-grab: C++ libcamera hardware capture helper with synchronized LM3643 IR strobe
- Howdy recorder plugins with ST VL53L5 8x8 ToF 3D contour anti-spoofing verification
- udev permissions for IR strobe and camera sensors
- PAM / Polkit authentication helper scripts for system-wide facial unlock

%prep
%setup -q -c -T -D
if [ -f "%{_sourcedir}/%{name}-%{version}.tar.zst" ]; then
    tar -xf "%{_sourcedir}/%{name}-%{version}.tar.zst" --strip-components=1
elif ls %{_sourcedir}/%{name}*.tar.* 1>/dev/null 2>&1; then
    tar -xf $(ls %{_sourcedir}/%{name}*.tar.* | head -n 1) --strip-components=1
elif [ -d "%{_sourcedir}/tools" ]; then
    cp -a %{_sourcedir}/{tools,howdy,udev,enable_polkit_howdy.sh,disable_polkit_howdy.sh,LICENSE,README.md} .
fi
rm -rf tools/ir-grab/build

%build
meson setup tools/ir-grab/build tools/ir-grab --prefix=%{_prefix}
ninja -C tools/ir-grab/build

%install
# Install ir-grab helper tool
install -D -m 0755 tools/ir-grab/build/ir-grab %{buildroot}%{_libexecdir}/howdy/ir-grab

# Install udev rule for IR strobe
install -D -m 0644 udev/99-lm3643-torch.rules %{buildroot}%{_udevrulesdir}/99-lm3643-torch.rules

# Install Howdy recorder plugins
install -D -m 0644 howdy/recorders/ir_libcamera_reader.py %{buildroot}%{_prefix}/lib64/howdy/recorders/ir_libcamera_reader.py
install -D -m 0644 howdy/recorders/tof_verifier.py %{buildroot}%{_prefix}/lib64/howdy/recorders/tof_verifier.py
install -D -m 0644 howdy/recorders/video_capture.py %{buildroot}%{_prefix}/lib64/howdy/recorders/video_capture.py

# Install Howdy example configuration
install -D -m 0644 howdy/config.ini.example %{buildroot}%{_datadir}/howdy/config.ini.example

# Install Polkit helper scripts
install -D -m 0755 enable_polkit_howdy.sh %{buildroot}%{_sbindir}/enable_polkit_howdy.sh
install -D -m 0755 disable_polkit_howdy.sh %{buildroot}%{_sbindir}/disable_polkit_howdy.sh

%post
%udev_rules_update

%postun
%udev_rules_update

%files
%license LICENSE
%doc README.md
%dir %{_libexecdir}/howdy
%{_libexecdir}/howdy/ir-grab
%{_udevrulesdir}/99-lm3643-torch.rules
%dir %{_prefix}/lib64/howdy
%dir %{_prefix}/lib64/howdy/recorders
%{_prefix}/lib64/howdy/recorders/ir_libcamera_reader.py
%{_prefix}/lib64/howdy/recorders/tof_verifier.py
%{_prefix}/lib64/howdy/recorders/video_capture.py
%dir %{_datadir}/howdy
%{_datadir}/howdy/config.ini.example
%{_sbindir}/enable_polkit_howdy.sh
%{_sbindir}/disable_polkit_howdy.sh

%changelog

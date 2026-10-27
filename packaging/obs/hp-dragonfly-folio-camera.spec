#
# spec file for package hp-dragonfly-folio-camera
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

Name:           hp-dragonfly-folio-camera
Version:        0.1.2
Release:        0
Summary:        Linux camera drivers and IR tools for HP Dragonfly Folio 13.5-inch G3
License:        GPL-2.0-only
Group:          Hardware/Camera
URL:            https://github.com/bamarc/dragonfly-folio-camera-mod
ExclusiveArch:  x86_64
Source0:        preamble
BuildRequires:  %{kernel_module_package_buildreqs}
BuildRequires:  gcc-c++
BuildRequires:  kernel-default-devel
BuildRequires:  kernel-devel
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(udev)
BuildRequires:  zstd
Recommends:     hp-dragonfly-folio-howdy
Recommends:     hp-presence

%kernel_module_package -p %{SOURCE0}

%description
Custom Linux kernel drivers and power-management configuration for the
HP Dragonfly Folio 13.5" G3 (Intel 12th Gen Alder Lake-U15, IPU6).
Enables the RGB camera (OV08A10), monochrome IR camera (OG0VA1B / OG0VE1B),
and TI LM3643 IR strobe LED.

%prep
%setup -q -c -T -D
if [ -f "%{_sourcedir}/%{name}-%{version}.tar.zst" ]; then
    tar -xf "%{_sourcedir}/%{name}-%{version}.tar.zst" --strip-components=1
elif [ -d "%{_sourcedir}/drivers" ]; then
    cp -a %{_sourcedir}/{drivers,tools,howdy,udev,Makefile,install.sh,enable_polkit_howdy.sh,disable_polkit_howdy.sh,LICENSE,README.md} .
fi

%build
# Build kernel modules for all kernel flavors (default)
for flavor in %{flavors_to_build}; do
    rm -rf "obj/$flavor"
    mkdir -p "obj/$flavor"
    cp -r drivers "obj/$flavor/"
    KSRC="%{kernel_source $flavor}"
    for moddir in int3472 ov08a10 og0va1b lm3643 ipu-bridge; do
        %make_build -C "$KSRC" M="$PWD/obj/$flavor/drivers/$moddir" modules
    done
done

%install
# Install kernel modules to updates directory
export INSTALL_MOD_PATH=%{buildroot}
export INSTALL_MOD_DIR=%{kernel_module_package_moddir}
for flavor in %{flavors_to_build}; do
    KSRC="%{kernel_source $flavor}"
    for moddir in int3472 ov08a10 og0va1b lm3643 ipu-bridge; do
        make -C "$KSRC" M="$PWD/obj/$flavor/drivers/$moddir" modules_install
    done
done

# Install udev rules for IR strobe and power management
install -D -m 0644 udev/99-lm3643-torch.rules %{buildroot}%{_udevrulesdir}/99-lm3643-torch.rules
install -D -m 0644 udev/99-hp-camera-pm.rules %{buildroot}%{_udevrulesdir}/99-hp-camera-pm.rules

# Install systemd sleep hook for Modern Standby (s2idle) resume
install -D -m 0755 tools/hp-camera-sleep.sh %{buildroot}%{_prefix}/lib/systemd/system-sleep/hp-camera-sleep.sh

%post
%udev_rules_update
udevadm trigger --subsystem-match=pci --action=add || true
udevadm trigger --subsystem-match=platform --action=add || true
udevadm trigger --subsystem-match=leds --action=change || true

%postun
%udev_rules_update

%files
%license LICENSE
%doc README.md
%{_udevrulesdir}/99-lm3643-torch.rules
%{_udevrulesdir}/99-hp-camera-pm.rules
%{_prefix}/lib/systemd/system-sleep/hp-camera-sleep.sh

%changelog


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
Version:        0.1.0
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
BuildRequires:  libcamera-devel
BuildRequires:  meson
BuildRequires:  ninja
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(udev)
BuildRequires:  zstd

%kernel_module_package -p %{SOURCE0}

%description
Custom Linux kernel drivers, hardware fixes, and facial authentication tools
for the HP Dragonfly Folio 13.5" G3 (Intel 12th Gen Alder Lake-U15, IPU6).
Enables the RGB camera (OV08A10), monochrome IR camera (OG0VA1B / OG0VE1B),
TI LM3643 IR strobe, and Howdy facial authentication.

%prep
%setup -q -c -T -D
if [ -f "%{_sourcedir}/%{name}-%{version}.tar.zst" ]; then
    tar -xf "%{_sourcedir}/%{name}-%{version}.tar.zst" --strip-components=1
elif [ -d "%{_sourcedir}/drivers" ]; then
    cp -a %{_sourcedir}/{drivers,tools,howdy,udev,Makefile,install.sh,enable_polkit_howdy.sh,disable_polkit_howdy.sh,LICENSE,README.md} .
fi
rm -rf tools/ir-grab/build

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

# Build userland ir-grab tool
meson setup tools/ir-grab/build tools/ir-grab --prefix=%{_prefix}
ninja -C tools/ir-grab/build

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

# Install ir-grab helper tool
install -D -m 0755 tools/ir-grab/build/ir-grab %{buildroot}%{_libexecdir}/howdy/ir-grab

# Install udev rule for IR strobe
install -D -m 0644 udev/99-lm3643-torch.rules %{buildroot}%{_udevrulesdir}/99-lm3643-torch.rules

# Install Howdy recorder plugins
install -D -m 0644 howdy/recorders/ir_libcamera_reader.py %{buildroot}%{_prefix}/lib64/howdy/recorders/ir_libcamera_reader.py
install -D -m 0644 howdy/recorders/video_capture.py %{buildroot}%{_prefix}/lib64/howdy/recorders/video_capture.py

# Install Polkit helper scripts
install -D -m 0755 enable_polkit_howdy.sh %{buildroot}%{_sbindir}/enable_polkit_howdy.sh
install -D -m 0755 disable_polkit_howdy.sh %{buildroot}%{_sbindir}/disable_polkit_howdy.sh

%files
%license LICENSE
%doc README.md
%dir %{_libexecdir}/howdy
%{_libexecdir}/howdy/ir-grab
%{_udevrulesdir}/99-lm3643-torch.rules
%dir %{_prefix}/lib64/howdy
%dir %{_prefix}/lib64/howdy/recorders
%{_prefix}/lib64/howdy/recorders/ir_libcamera_reader.py
%{_prefix}/lib64/howdy/recorders/video_capture.py
%{_sbindir}/enable_polkit_howdy.sh
%{_sbindir}/disable_polkit_howdy.sh

%changelog

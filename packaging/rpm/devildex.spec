Name:           devildex
Version:        0.2.1
Release:        1%{?dist}
Summary:        A tool for managing documentation.

License:        MIT
URL:            https://github.com/magowiz/devildex
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pip
BuildRequires:  python3-wheel


%description
Devildex is a comprehensive tool designed to streamline the management
and generation of various documentation formats.

%prep
%setup -q

%build
%py3_build

%install
%py3_install

%files
%license LICENSE
%{python3_sitelib}/%{name}
%{python3_sitelib}/%{name}-%{version}.dist-info/

%changelog
* Sat Oct 04 2025 magowiz <magowiz@gmail.com> - 0.2.1-1
- Initial RPM package creation.

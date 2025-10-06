%{?_disable_debug_package}
%global debug_package %{nil}
Name:           devildex
Version:        0.2.1
%global __requires_exclude ^python3\\.13dist\\(.*\\)$
Release:        1%{?dist}
Summary:        A tool for managing documentation.

License:        MIT
URL:            https://github.com/magowiz/devildex
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
AutoReq: no
AutoProv: no
Requires:       python3
Requires:       SDL2

%description
Devildex is a comprehensive tool designed to streamline the management
and generation of various documentation formats.

%prep
%setup -q

%build
poetry build --format wheel

%install
pip install --prefix %{buildroot}/usr dist/*.whl

# Explicitly install scripts
mkdir -p %{buildroot}%{_bindir}
install -m 0755 %{_builddir}/%{name}-%{version}/scripts/devildex %{buildroot}%{_bindir}/devildex
install -m 0755 %{_builddir}/%{name}-%{version}/scripts/devildex-alembic %{buildroot}%{_bindir}/devildex-alembic
install -m 0755 %{_builddir}/%{name}-%{version}/scripts/devildex-gemini-setup %{buildroot}%{_bindir}/devildex-gemini-setup
install -m 0755 %{_builddir}/%{name}-%{version}/scripts/devildex-register-project %{buildroot}%{_bindir}/devildex-register-project

# Explicitly install the scripts directory into site-packages
mkdir -p %{buildroot}%{python3_sitelib}/scripts
cp -r %{_builddir}/%{name}-%{version}/scripts/* %{buildroot}%{python3_sitelib}/scripts/

%files
%license LICENSE
%{_bindir}/devildex
%{_bindir}/devildex-alembic
%{_bindir}/devildex-gemini-setup
%{_bindir}/devildex-register-project
%{python3_sitelib}/%{name}
%{python3_sitelib}/%{name}-%{version}.dist-info/
%{python3_sitelib}/scripts/

%changelog
* Sat Oct 04 2025 magowiz <magowiz@gmail.com> - 0.2.1-1
- Initial RPM package creation.
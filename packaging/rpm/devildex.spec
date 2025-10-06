%{?_disable_debug_package}
%global debug_package %{nil}
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
BuildRequires:  pyproject-rpm-macros
Requires:       SDL2
Requires:       python3-toml >= 0.10.2
Requires:       python3-pip-requirements-parser >= 32.0.1
Requires:       python3-pdoc3 >= 0.11.6
Requires:       python3-requests >= 2.32.4
Requires:       python3-platformdirs >= 3.0.0
Requires:       python3-poetry-core >= 2.0.0
Requires:       python3-sqlalchemy >= 2.0.41
Requires:       python3-pyyaml >= 6.0.2
Requires:       python3-pydoctor >= 25.4.0
# wxpython is a direct URL dependency, usually not handled by RPM Requires.
# Assuming it's installed via pip in the build process.
Requires:       python3-fastmcp >= 2.12.2
Requires:       python3-fastapi >= 0.116.1
Requires:       python3-uvicorn >= 0.35.0
Requires:       python3-markdownify >= 1.2.0
Requires:       python3-pyinstaller >= 6.16.0
Requires:       python3-alembic >= 1.13.1

%description
Devildex is a comprehensive tool designed to streamline the management
and generation of various documentation formats.

%prep
%setup -q

%build
poetry build --format wheel

%install
pip install --prefix %{buildroot}/usr --no-deps dist/*.whl

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
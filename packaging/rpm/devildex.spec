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
Provides: python3.13dist(fastapi) < 0.117~~
Provides: python3.13dist(fastmcp) < 3~~
Provides: python3.13dist(markdownify) < 2~~
Provides: python3.13dist(pdoc3) < 0.12~~
Provides: python3.13dist(pydoctor) < 26~~

%description
Devildex is a comprehensive tool designed to streamline the management
and generation of various documentation formats.

%prep
%setup -q

%build
poetry build --format wheel
%install
%pyproject_install
find %{buildroot}%{python3_sitelib} -type f > python_files.lst

%files
%license LICENSE
%{_bindir}/devildex
%{_bindir}/devildex-alembic
%{_bindir}/devildex-gemini-setup
%{_bindir}/devildex-register-project
%{python3_sitelib}/%{name}
%{python3_sitelib}/%{name}-%{version}.dist-info/
%{python3_sitelib}/scripts/
%{python3_sitelib}/


%changelog
* Mon Oct 06 2025 magowiz <magowiz@gmail.com> - 0.2.0-1
- Initial RPM release
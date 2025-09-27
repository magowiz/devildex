import logging
from sqlalchemy.orm import Session as SQLAlchemySession
from .models import (
    Docset,
    PackageInfo,
    RegisteredProject,
    project_docset_association,
)

logger = logging.getLogger(__name__)

def populate_with_sample_data(main_session: SQLAlchemySession) -> None:
    """Populate the database with sample data for development and testing."""
    logger.info("Populating database with sample data...")

    # Clear existing data
    main_session.execute(project_docset_association.delete())
    main_session.query(Docset).delete()
    main_session.query(PackageInfo).delete()
    main_session.query(RegisteredProject).delete()
    main_session.commit()

    # Create sample projects
    project1 = RegisteredProject(
        project_name="WebAppProject",
        project_path="/path/to/webapp",
        python_executable="/path/to/webapp/.venv/bin/python",
    )
    project2 = RegisteredProject(
        project_name="DataAnalysisProject",
        project_path="/path/to/dataanalysis",
        python_executable="/path/to/dataanalysis/.venv/bin/python",
    )
    main_session.add_all([project1, project2])
    main_session.commit()

    # Create sample package info
    pkg_info_requests = PackageInfo(
        package_name="requests",
        summary="Elegant and simple HTTP library for Python, built for human beings.",
        project_urls={
            "Homepage": "https://requests.readthedocs.io/",
            "Documentation": "https://requests.readthedocs.io/en/latest/",
            "Source": "https://github.com/psf/requests",
        },
    )
    pkg_info_pandas = PackageInfo(
        package_name="pandas",
        summary="Powerful data structures for data analysis, time series, and statistics",
    )
    pkg_info_flask = PackageInfo(package_name="Flask")
    main_session.add_all([pkg_info_requests, pkg_info_pandas, pkg_info_flask])
    main_session.commit()

    # Create sample docsets
    docset_requests_v1 = Docset(
        package_info=pkg_info_requests,
        package_name="requests",
        package_version="2.28.1",
        status="available",
    )
    docset_requests_v2 = Docset(
        package_info=pkg_info_requests,
        package_name="requests",
        package_version="2.29.0",
        status="generating",
    )
    docset_pandas_v1 = Docset(
        package_info=pkg_info_pandas,
        package_name="pandas",
        package_version="1.5.0",
        status="available",
    )
    docset_flask_v1 = Docset(
        package_info=pkg_info_flask,
        package_name="Flask",
        package_version="2.2.2",
        status="error",
    )
    main_session.add_all(
        [docset_requests_v1, docset_requests_v2, docset_pandas_v1, docset_flask_v1]
    )
    main_session.commit()

    # Associate docsets with projects
    project1.docsets.append(docset_requests_v1)
    project1.docsets.append(docset_flask_v1)
    project2.docsets.append(docset_requests_v2)
    project2.docsets.append(docset_pandas_v1)
    main_session.commit()

    logger.info("Sample data population complete.")

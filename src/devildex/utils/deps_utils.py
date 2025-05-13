"""deps utils module."""

import logging
from pathlib import Path

from pip_requirements_parser import RequirementsFile

logger = logging.getLogger(__name__)


def _process_requirements_obj(
    requirements_file_obj: RequirementsFile,
    file_path_for_logging: Path,
    lines_to_explicitly_remove: set[str],
) -> list[str]:
    """Processes a RequirementsFile object to extract valid lines and log invalid ones."""
    valid_lines: list[str] = []

    # Process valid requirements and filter out specific lines
    for req in requirements_file_obj.requirements:
        if req.line:
            stripped_line = req.line.strip()
            if stripped_line in lines_to_explicitly_remove:
                logger.info(
                    "Rimozione esplicita della riga '%s' da '%s'",
                    stripped_line,
                    file_path_for_logging,
                )
            else:
                # Add the original, unstripped line as it was validly parsed
                valid_lines.append(req.line)

    # Log information about invalid lines found by the parser
    if requirements_file_obj.invalid_lines:
        # Count invalid lines that actually have content
        invalid_line_content_count = sum(
            1
            for inv_line in requirements_file_obj.invalid_lines
            if inv_line.line and inv_line.line.strip()
        )
        if invalid_line_content_count > 0:
            logger.warning(
                "Trovate %s righe potenzialmente non valide (scartate dal parser) in '%s'.",
                invalid_line_content_count,
                file_path_for_logging,
            )
    return valid_lines


def filter_requirements_lines(file_path_str: str) -> list[str] | None:
    """Legge un file requirements.txt, filtra le righe non valide.

    usando pip-requirements-parser e restituisce una lista delle stringhe di
    requisito valide.

    Args:
        file_path_str (str): Il percorso al file requirements.txt da leggere.

    Returns:
        list[str] | None: Una lista di stringhe, ognuna rappresentante una riga
                          di requisito valida. Restituisce None se il file non
                          può essere letto, la libreria non è disponibile, o si
                          verifica un errore imprevisto. Restituisce una lista
                          vuota se non ci sono requisiti validi.
    """
    if RequirementsFile is None:
        logger.error(
            "La libreria 'pip-requirements-parser' non è installata. "
            "Impossibile filtrare il file requirements."
        )
        return None

    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.error("Il file requirements '%s' non trovato.", file_path)
        return None

    lines_to_explicitly_remove = {"-e .", "-e."}

    try:
        logger.debug("Tentativo di parsificare e filtrare: %s", file_path)
        # This call can raise exceptions if the file is malformed or unreadable
        requirements_file_obj = RequirementsFile.from_file(str(file_path))

        valid_lines = _process_requirements_obj(
            requirements_file_obj, file_path, lines_to_explicitly_remove
        )

        logger.debug(
            "Numero di righe valide estratte da '%s': %s", file_path, len(valid_lines)
        )
        return valid_lines

    except Exception as e:
        logger.error(
            "Errore imprevisto durante la parsificazione del file '%s' "
            "con pip-requirements-parser: %s",
            file_path,
            e,
        )
        return None

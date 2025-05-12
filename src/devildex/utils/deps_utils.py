"""deps utils module."""
import logging
from pathlib import Path

from pip_requirements_parser import RequirementsFile

logger = logging.getLogger(__name__)


def filter_requirements_lines(file_path_str: str) -> list[str] | None:
    """Legge un file requirements.txt, filtra le righe non valide.

    usando pip-requirements-parser e restituisce una lista delle stringhe di requisito valide.

    Args:
        file_path_str (str): Il percorso al file requirements.txt da leggere.

    Returns:
        list: Una lista di stringhe, ognuna rappresentante una riga di requisito valida.
              Restituisce None se il file non può essere letto, la libreria non è
              disponibile, o si verifica un errore imprevisto.
              Restituisce una lista vuota se non ci sono requisiti validi.
    """
    if RequirementsFile is None:
        logger.error(
            "La libreria 'pip-requirements-parser' non è installata. "
            "Impossibile filtrare il file requirements."
        )
        return None

    valid_lines: list[str] = []
    invalid_lines_found: list[str] = []
    file_path = Path(file_path_str)  # Converti in Path per coerenza

    if not file_path.exists():
        logger.error("Il file requirements '%s' non trovato.", file_path)
        return None

    try:
        logger.debug("Tentativo di parsificare e filtrare: %s", file_path)
        requirements_file_obj = RequirementsFile.from_file(
            str(file_path)
        )

        for req in requirements_file_obj.requirements:
            if req.line:
                valid_lines.append(req.line)

        for invalid_line_obj in requirements_file_obj.invalid_lines:
            if invalid_line_obj.line:
                invalid_lines_found.append(invalid_line_obj.line)

        if invalid_lines_found:
            logger.warning(
                "Riga Trovate %s righe potenzialmente non valide in '%s'. "
                "Sono state scartate dal parser.",
                len(invalid_lines_found), file_path
            )
            for line in invalid_lines_found:
                logger.debug("  Riga scartata: %s", line.strip())
        final_valid_lines: list[str] = []
        lines_to_explicitly_remove = {"-e .", "-e."}

        for line in valid_lines:
            stripped_line = line.strip()
            if stripped_line in lines_to_explicitly_remove:
                logger.info(
                    "Rimozione esplicita della riga '%s' da '%s'",
                    stripped_line, file_path
                )
            else:
                final_valid_lines.append(line)
        valid_lines = final_valid_lines
        logger.debug(
            "Numero di righe valide estratte da '%s': %s",
            file_path, len(valid_lines)
        )
        return valid_lines

    except Exception as e:
        logger.error(
            "Errore imprevisto durante la parsificazione del file '%s' "
            "con pip-requirements-parser: %s",
            file_path, e
        )
        return None

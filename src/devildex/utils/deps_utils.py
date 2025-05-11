import logging
from pathlib import Path


from pip_requirements_parser import RequirementsFile

logger = logging.getLogger(__name__)


def filter_requirements_lines(file_path_str: str) -> list[str] | None:
    """
    Legge un file requirements.txt, filtra le righe non valide
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
        return None  # O potresti voler restituire le righe originali non filtrate

    valid_lines: list[str] = []
    invalid_lines_found: list[str] = []
    file_path = Path(file_path_str)  # Converti in Path per coerenza

    if not file_path.exists():
        logger.error(f"Il file requirements '{file_path}' non trovato.")
        return None

    try:
        logger.debug(f"Tentativo di parsificare e filtrare: {file_path}")
        requirements_file_obj = RequirementsFile.from_file(
            str(file_path)
        )  # La libreria vuole una stringa

        for req in requirements_file_obj.requirements:
            if req.line:  # Assicurati che la linea non sia vuota
                valid_lines.append(req.line)

        for invalid_line_obj in requirements_file_obj.invalid_lines:
            if invalid_line_obj.line:  # Assicurati che la linea non sia vuota
                invalid_lines_found.append(invalid_line_obj.line)

        if invalid_lines_found:
            logger.warning(
                f"Trovate {len(invalid_lines_found)} righe potenzialmente non valide in '{file_path}'. "
                "Sono state scartate dal parser."
            )
            for line in invalid_lines_found:
                logger.debug(f"  Riga scartata: {line.strip()}")
        final_valid_lines: list[str] = []
        lines_to_explicitly_remove = {"-e .", "-e."}

        for line in valid_lines:
            stripped_line = line.strip()
            if stripped_line in lines_to_explicitly_remove:
                logger.info(
                    f"Rimozione esplicita della riga '{stripped_line}' da '{file_path}'"
                )
            else:
                final_valid_lines.append(line)
        valid_lines = final_valid_lines
        logger.debug(
            f"Numero di righe valide estratte da '{file_path}': {len(valid_lines)}"
        )
        return valid_lines

    except Exception as e:
        logger.error(
            f"Errore imprevisto durante la parsificazione del file '{file_path}' "
            f"con pip-requirements-parser: {e}"
        )
        return None

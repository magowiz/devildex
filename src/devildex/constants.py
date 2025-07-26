"""constants module."""

CONF_FILENAME = "conf.py"
AVAILABLE_BTN_LABEL = "📖 Available"
ERROR_BTN_LABEL = "❌ Error"
NOT_AVAILABLE_BTN_LABEL = "Not Available"
COLUMNS_ORDER: list[str] = [
    "id",
    "name",
    "version",
    "description",
    "status",
    "docset_status",
]
COL_WIDTH_ID = 60
COL_WIDTH_DESC = 200
COL_WIDTH_STATUS = 120
COL_WIDTH_DOCSET_STATUS = 140
COL_WIDTH_VERSION = 80
COL_WIDTH_NAME = 160
COL_WIDTHS: dict[str, int] = {
    "id": COL_WIDTH_ID,
    "name": COL_WIDTH_NAME,
    "version": COL_WIDTH_VERSION,
    "description": COL_WIDTH_DESC,
    "status": COL_WIDTH_STATUS,
    "docset_status": COL_WIDTH_DOCSET_STATUS,
}

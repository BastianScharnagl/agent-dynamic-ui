from google.genai import types
from agent.ui.schema import SUPPORTED_ELEMENTS, GUI_ELEMENT_SCHEMA

def render_custom_gui(
    form_id: str,
    headline: str,
    elements: list[dict],
    submit_label: str,
    description: str | None = None,
) -> dict:
    """Validiert die vom Agenten erzeugten Formulardaten und gibt sie fürs UI zurück."""
    if not form_id.strip():
        raise ValueError("form_id darf nicht leer sein")
    if not headline.strip():
        raise ValueError("headline darf nicht leer sein")
    if not submit_label.strip():
        raise ValueError("submit_label darf nicht leer sein")
    if not elements:
        raise ValueError("Das Formular muss mindestens ein Element enthalten")

    field_ids: set[str] = set()
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            raise ValueError(f"Formularelement {index} muss ein Objekt sein")

        element_id = element.get("id")
        if not isinstance(element_id, str) or not element_id.strip():
            raise ValueError(f"Formularelement {index} benötigt eine id")
        if element_id in field_ids:
            raise ValueError(f"Doppelte Formularfeld-ID: {element_id}")
        field_ids.add(element_id)

        if element.get("element") not in SUPPORTED_ELEMENTS:
            raise ValueError(
                f"Nicht unterstützter Feldtyp für Formularfeld '{element_id}'"
            )
        if not isinstance(element.get("label"), str) or not element["label"].strip():
            raise ValueError(f"Formularfeld '{element_id}' benötigt ein label")
        if element["element"] == "select" and not element.get("options"):
            raise ValueError(f"Auswahlfeld '{element_id}' benötigt Optionen")

    return {
        "form_id": form_id,
        "headline": headline,
        "description": description,
        "elements": elements,
        "submit_label": submit_label,
    }

RENDER_CUSTOM_GUI_DECLARATION = types.FunctionDeclaration(
    name="render_custom_gui",
    description=(
        "Zeigt ein dynamisches Formular an, wenn Angaben oder eine Bestätigung "
        "des Nutzers benötigt werden. Gib für jedes Feld eine eindeutige ID, "
        "einen unterstützten Feldtyp und ein Label an."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "form_id": types.Schema(type="STRING", description="Eindeutige Formular-ID"),
            "headline": types.Schema(type="STRING", description="Überschrift des Formulars"),
            "description": types.Schema(type="STRING", description="Optionale Beschreibung"),
            "elements": types.Schema(
                type="ARRAY",
                items=GUI_ELEMENT_SCHEMA,
                description="Felder des Formulars",
            ),
            "submit_label": types.Schema(
                type="STRING",
                description="Beschriftung des Absende-Buttons",
            ),
        },
        required=["form_id", "headline", "elements", "submit_label"]
    )
)

UI_TOOL = types.Tool(
    function_declarations=[
        RENDER_CUSTOM_GUI_DECLARATION
    ]
)
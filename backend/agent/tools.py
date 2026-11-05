from google.genai import types

SUPPORTED_ELEMENTS = {
    "text_input",
    "number_input",
    "textarea",
    "select",
    "date_picker",
    "checkbox",
}


# 1. Validierungsregeln
VALIDATION_RULE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "min": types.Schema(type="NUMBER", description="Minimalwert (für Zahlen) oder Mindestlänge (für Text)"),
        "max": types.Schema(type="NUMBER", description="Maximalwert (für Zahlen) oder Maximallänge (für Text)"),
        "pattern": types.Schema(type="STRING", description="Regex-Muster zur Validierung (z.B. '^[A-Z]{2}[0-9]{4}$')"),
        "error_message": types.Schema(type="STRING", description="Benutzerfreundliche Fehlermeldung bei Validierungsfehler")
    }
)

# 2. Bedingte Sichtbarkeit (Conditional Visibility)
VISIBILITY_CONDITION_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "depends_on": types.Schema(type="STRING", description="ID des Feldes, von dem die Sichtbarkeit abhängt"),
        "operator": types.Schema(
            type="STRING",
            enum=["equals", "not_equals", "greater_than", "less_than", "contains"],
            description="Vergleichsoperator"
        ),
        "value": types.Schema(type="STRING", description="Zielwert für den Vergleich")
    },
    required=["depends_on", "operator", "value"]
)

# 3. Atomares GUI-Element mit Validierung und Sichtbarkeit
GUI_ELEMENT_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "id": types.Schema(type="STRING", description="Eindeutige Feld-ID"),
        "element": types.Schema(
            type="STRING",
            enum=["text_input", "number_input", "textarea", "select", "date_picker", "checkbox"],
            description="Komponententyp"
        ),
        "label": types.Schema(type="STRING", description="Feldbezeichnung"),
        "placeholder": types.Schema(type="STRING"),
        "required": types.Schema(type="BOOLEAN"),
        "options": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
        "default_value": types.Schema(type="STRING"),
        "validation": VALIDATION_RULE_SCHEMA,
        "visibility": VISIBILITY_CONDITION_SCHEMA
    },
    required=["id", "element", "label"]
)


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


# Tool-Deklaration für Gemini
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
from google.genai import types

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

# Tool-Deklaration für Gemini
RENDER_CUSTOM_GUI_DECLARATION = types.FunctionDeclaration(
    name="render_custom_gui",
    description="Rendert ein Formular mit Validierungsregeln und bedingter Sichtbarkeit.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "form_id": types.Schema(type="STRING"),
            "headline": types.Schema(type="STRING"),
            "description": types.Schema(type="STRING"),
            "elements": types.Schema(type="ARRAY", items=GUI_ELEMENT_SCHEMA),
            "submit_label": types.Schema(type="STRING")
        },
        required=["form_id", "headline", "elements", "submit_label"]
    )
)

UI_TOOL = types.Tool(
    function_declarations=[
        RENDER_CUSTOM_GUI_DECLARATION  # bzw. RENDER_UI_DECLARATION
    ]
)
import os
import tempfile
from pathlib import Path

from django.conf import settings

from .constants import REPORT_COLUMNS
from .helpers import split_csv


def _get_nested_value(data, path, default=None):
    current = data
    for key in path:
        if isinstance(current, list):
            if not current:
                return default
            current = current[0]
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _join_titles(items):
    if not items:
        return ""
    if isinstance(items, list):
        return ", ".join(
            str(item.get("title") or item.get("name") or "").strip()
            for item in items
            if isinstance(item, dict) and (item.get("title") or item.get("name"))
        )
    return ""


def _format_measure(piece, keys):
    values = [piece.get(key) for key in keys]
    if not any(value not in (None, "", "None") for value in values):
        return ""

    height, width, depth, diameter = values
    parts = []
    if height not in (None, "", "None"):
        parts.append(str(height))
    if width not in (None, "", "None"):
        parts.append(str(width))
    if depth not in (None, "", "None"):
        parts.append(str(depth))

    measure = " x ".join(parts)
    if diameter not in (None, "", "None"):
        measure = f"{measure} ø {diameter}" if measure else f"ø {diameter}"
    return measure.strip()


def _resolve_inventory_image_path(piece):
    file_name = _get_nested_value(piece, ["photo_thumb_info", "file_name"])
    if not file_name:
        return None

    image_path = Path( settings.THUMBNAILS_INVENTORY_PATH) / file_name
    return image_path if image_path.exists() else None


def _resolve_research_image_path(piece):
    file_name = _get_nested_value(piece, ["photo_research_info", "file_name"])
    if not file_name:
        return None

    image_path = Path(settings.THUMBNAILS_RESEARCH_PATH) / file_name
    return image_path if image_path.exists() else None


def _filesystem_path_to_static_url(path_obj):
    normalized = str(path_obj).replace("\\", "/")
    marker = "/static/"
    if marker not in normalized:
        return None
    return normalized[normalized.index(marker) :]


def resolve_report_value(piece, column_id):
    direct_map = {
        "inventory_number": piece.get("inventory_number"),
        "catalog_number": piece.get("catalog_number"),
        "origin_number": piece.get("origin_number"),
        "description_origin": piece.get("description_origin"),
        "description_inventory": piece.get("description_inventory"),
        "appraisal": piece.get("appraisal"),
        "tags": piece.get("tags"),
        "research.title": _get_nested_value(piece, ["research_info", "title"]),
        "research.technique": _get_nested_value(piece, ["research_info", "technique"]),
        "research.materials": _get_nested_value(piece, ["research_info", "materials"]),
        "research.creation_date": _get_nested_value(
            piece, ["research_info", "creation_date"]
        ),
        "research.acquisition_form": _get_nested_value(
            piece, ["research_info", "acquisition_form"]
        ),
        "research.acquisition_source": _get_nested_value(
            piece, ["research_info", "acquisition_source"]
        ),
        "research.acquisition_date": _get_nested_value(
            piece, ["research_info", "acquisition_date"]
        ),
        "research.firm_description": _get_nested_value(
            piece, ["research_info", "firm_description"]
        ),
        "research.short_description": _get_nested_value(
            piece, ["research_info", "short_description"]
        ),
        "research.formal_description": _get_nested_value(
            piece, ["research_info", "formal_description"]
        ),
        "research.observation": _get_nested_value(
            piece, ["research_info", "observation"]
        ),
        "research.publications": _get_nested_value(
            piece, ["research_info", "publications"]
        ),
        "research.card": _get_nested_value(piece, ["research_info", "card"]),
        "gender.title": _get_nested_value(piece, ["genders_info", "title"]),
        "subgender.title": _get_nested_value(piece, ["subgenders_info", "title"]),
        "type_object.title": _get_nested_value(piece, ["type_object_info", "title"]),
        "dominant_material.title": _get_nested_value(
            piece, ["dominant_material_info", "title"]
        ),
        "location.name": _get_nested_value(piece, ["location_info", "name"]),
        "piece.set.title": _join_titles(piece.get("set_info")),
        "research.authors": _join_titles(piece.get("authors_info")),
        "research.involved_creation_ids": _join_titles(
            piece.get("involved_creation_info")
        ),
        "research.period.title": _join_titles(piece.get("period_info")),
        "research.place_of_creation.title": _join_titles(
            _get_nested_value(piece, ["research_info", "place_of_creation_info"], [])
        ),
    }

    if column_id == "measure_without":
        return _format_measure(piece, ["height", "width", "depth", "diameter"])
    if column_id == "measure_with":
        return _format_measure(
            piece,
            ["height_with_base", "width_with_base", "depth_with_base", "diameter_with_base"],
        )
    if column_id == "photo_inventory":
        return _resolve_inventory_image_path(piece)
    if column_id == "photo_research":
        return _resolve_research_image_path(piece)

    value = direct_map.get(column_id)
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item not in (None, ""))
    return value


def build_piece_section(piece, selected_columns, image=None):
    piece_id = str(piece.get("_id"))

    title = (
        _get_nested_value(piece, ["research_info", "title"])
        or piece.get("description_inventory")
        or piece.get("description_origin")
        or f"Pieza {piece_id}"
    )

    section = {
        "id": piece_id,
        "_id": piece_id,
        "title": title,
        "inventory_number": piece.get("inventory_number") or "",
        "catalog_number": piece.get("catalog_number") or "",
        "origin_number": piece.get("origin_number") or "",
        "inventory_photo_file_name": _get_nested_value(
            piece, ["photo_thumb_info", "file_name"]
        ),
        "fields": [],
    }

    # 🔥 Imagen principal (la nueva)
    if image:
        section["fields"].append({
            "id": "main_image",
            "label": "Imagen",
            "type": "image",
            "value": image,
            "file_path": image,
            "preview_url": _filesystem_path_to_static_url(image),
        })

    for column_id in selected_columns:
        value = resolve_report_value(piece, column_id)
        if value in (None, "", [], {}):
            continue

        is_image = hasattr(value, "exists")

        field = {
            "id": column_id,
            "label": REPORT_COLUMNS.get(column_id, column_id),
            "type": "image" if is_image else "text",
            "value": str(value),
        }

        if is_image:
            field["file_path"] = str(value)
            field["preview_url"] = _filesystem_path_to_static_url(value)

        section["fields"].append(field)

    return section


def build_report_markdown(report, rendered_pieces):
    lines = [f"# {report.get('name') or 'Reporte'}", ""]

    if report.get("description"):
        lines.extend([report["description"], ""])

    lines.extend(["## Resumen", ""])
    lines.append(f"- Tipo de seleccion: {report.get('select_type') or 'custom'}")
    lines.append(f"- Total de piezas: {len(rendered_pieces)}")

    if report.get("lending_list"):
        lines.append(f"- Institucion: {report.get('institution_name') or report.get('institution') or 'N/D'}")
        lines.append(f"- Exposicion: {report.get('exhibition_name') or report.get('exhibition') or 'N/D'}")
        if report.get("exhibition_date_start") or report.get("exhibition_date_end"):
            lines.append(
                f"- Fechas de exhibicion: {report.get('exhibition_date_start') or 'N/D'} a {report.get('exhibition_date_end') or 'N/D'}"
            )
    lines.append("")

    for index, piece in enumerate(rendered_pieces, start=1):
        section_title = piece.get("title") or f"Pieza {index}"
        lines.extend([f"## {index}. {section_title}", ""])
        lines.append(f"- No. inventario: {piece.get('inventory_number') or 'N/D'}")
        lines.append(f"- No. catalogo: {piece.get('catalog_number') or 'N/D'}")
        lines.append(f"- No. procedencia: {piece.get('origin_number') or 'N/D'}")
        lines.append("")

        for field in piece.get("fields", []):
            if field["type"] == "image":
                lines.append(f"### {field['label']}")
                lines.append("")
                lines.append(f"![{field['label']}]({field.get('file_path') or field['value']})")
                lines.append("")
            else:
                lines.append(f"- **{field['label']}:** {field['value']}")

        lines.append("")
        lines.append("\\newpage")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_report_pdf(report, rendered_pieces):
    import pypandoc

    markdown_content = build_report_markdown(report, rendered_pieces)

    with tempfile.TemporaryDirectory(prefix="report_pdf_") as temp_dir:
        temp_path = Path(temp_dir)
        markdown_path = temp_path / "report.md"
        pdf_path = temp_path / "report.pdf"
        markdown_path.write_text(markdown_content, encoding="utf-8")

        current_dir = os.getcwd()
        try:
            os.chdir(temp_dir)
            pypandoc.convert_file(
                str(markdown_path.name),
                "pdf",
                outputfile=str(pdf_path.name),
                extra_args=[
                    "--pdf-engine=xelatex",
                    "-V",
                    "geometry:margin=1in",
                    "-V",
                    "fontsize=11pt",
                ],
            )
        finally:
            os.chdir(current_dir)

        pdf_bytes = pdf_path.read_bytes()

    return markdown_content, pdf_bytes

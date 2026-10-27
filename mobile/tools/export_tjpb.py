"""Atualiza os assets do Android a partir do cofre, sem alterar as fontes."""

import argparse
import json
import shutil
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT))
from tjpb import TjpbCatalog  # noqa: E402


def export(vault: Path):
    assets = APP_ROOT / "mobile" / "assets"
    catalog = TjpbCatalog(vault)
    if catalog.errors:
        raise ValueError(" ".join(catalog.errors))
    payload = {
        "title": "TJPB · Desenvolvimento de Sistemas", "examDate": "2027-01-24",
        "revision": "2026-10-26", "topics": [
            {"id": topic.key, "group": topic.group, "text": topic.text}
            for topic in catalog.topics
        ], "exams": [], "documents": [],
    }
    (assets / "pdfs").mkdir(parents=True, exist_ok=True)
    for exam in catalog.exams:
        item = {"id": exam.key, "title": exam.title, "description": exam.description, "documents": {}}
        for kind, path in exam.files.items():
            document_id = f"{exam.key.removeprefix('exam:')}_{kind}"
            filename = f"{document_id}.pdf"
            shutil.copy2(path, assets / "pdfs" / filename)
            page = exam.answer_page if kind == "gabarito_definitivo" else (exam.mirror_page or 1) if kind == "espelho_discursiva" else 1
            label = {"prova": "Prova", "gabarito_definitivo": "Gabarito definitivo", "espelho_discursiva": "Espelho da discursiva"}[kind]
            payload["documents"].append({"id": document_id, "title": f"{label} · {exam.title}",
                "asset": f"assets/pdfs/{filename}", "kind": kind, "initialPage": page, "examId": exam.key})
            item["documents"][kind] = document_id
        payload["exams"].append(item)
    for filename, title in [
        ("edital_retificado_2026-10-26.pdf", "Edital TJPB · atualizado em 26/10"),
        ("primeira_retificacao_2026-10-26.pdf", "Primeira retificação · TJPB"),
    ]:
        shutil.copy2(vault / "Edital" / filename, assets / "pdfs" / filename)
        payload["documents"].append({"id": filename.removesuffix(".pdf"), "title": title,
            "asset": f"assets/pdfs/{filename}", "kind": "edital", "initialPage": 1})
    (assets / "data").mkdir(exist_ok=True)
    (assets / "data" / "catalog.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(payload['topics'])} tópicos, {len(payload['exams'])} provas, {len(payload['documents'])} PDFs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", type=Path, help="Pasta TJPB 2026 do Obsidian")
    export(parser.parse_args().vault)

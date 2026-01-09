import json

def load_request_data(request):
    changes = json.loads(request.data.get("Changes", "[]"))
    pics_new = json.loads(request.data.get("PicsNew", "[]"))
    changed_pics = json.loads(request.data.get("ChangedPics", "{}"))
    changes_pics_inputs = json.loads(request.data.get("ChangesPicsInputs", "[]"))
    new_footnotes = json.loads(request.data.get("NewFootnotes", "[]"))
    new_bibliographies = json.loads(request.data.get("NewBibliographies", "[]"))
    changes_bibliographies = json.loads(request.data.get("ChangesBibliographies", "[]"))
    changes_footnotes = json.loads(request.data.get("ChangesFootnotes", "[]"))
    new_docs = json.loads(request.data.get("DocumentsNew", "[]"))
    changes_docs = json.loads(request.data.get("ChangesDocs", "[]"))

    return (
        changes,
        pics_new,
        changed_pics,
        changes_pics_inputs,
        new_footnotes,
        new_bibliographies,
        changes_bibliographies,
        changes_footnotes,
        new_docs,
        changes_docs,
    )

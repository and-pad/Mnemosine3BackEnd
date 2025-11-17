import json

def load_request_data(request):
    changes = json.loads(request.data.get("formDatachanges", "{}"))
    changes_pics_inputs = json.loads(request.data.get("changedPicsInputs", "{}"))
    pics_new = json.loads(request.data.get("PicsNew", "{}"))
    changes_docs = json.loads(request.data.get("changedDocs", "{}"))
    new_docs = json.loads(request.data.get("DocumentsNew", "{}"))    
    changed_pics = json.loads(request.data.get("ChangedPics", "{}"))

    return (
        changes,
        pics_new,
        changed_pics,
        changes_pics_inputs,        
        new_docs,
        changes_docs,
    )

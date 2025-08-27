from hmac import new
from bson import ObjectId
from user_queries.driver_database.mongo import Mongo
from ..tools import AuditManager
from user_queries.shemas.research_update_payload import ResearchUpdatePayload
from user_queries.views.researchs.utils import get_research_id

def save_history_changes(_id, user_id, research, is_new_research, changes_data):
        
        changes = changes_data.get("changes")
        changes_pics_inputs = changes_data.get("changes_pics_inputs")
        changed_pics = changes_data.get("changed_pics")
        new_footnotes = changes_data.get("new_footnotes")
        ids_saved_footnotes = changes_data.get("ids_saved_footnotes")
        new_bibliographies = changes_data.get("new_bibliographies")
        changes_footnotes = changes_data.get("changes_footnotes")
        before_update_footnotes = changes_data.get("before_update_footnotes")
        changes_bibliographies = changes_data.get("changes_bibliographies")
        before_update_bibliographies = changes_data.get("before_update_bibliographies")        
        documents = changes_data.get("documents")
        ResearchChanges = Mongo().connect("research_changes_history")

        if any(
            isinstance(x, dict)
            for x in [
                changes,
                changes_pics_inputs,
                changed_pics,
                new_footnotes,
                changes_footnotes,
                new_bibliographies,
                changes_bibliographies,
                documents,
                                # changes_docs_inputs,
                #changed_docs,
            ]
        ):
           
            combined_changes = {}
            research_id = get_research_id(_id)
            print("research_id: ", research_id)
            # Combine changes into a single dictionary
            if research_id:                
                combined_changes["research_id"] = ObjectId(research_id)
            if changes:
                print("changes", changes)
                combined_changes["changes"] = changes

            if changes_pics_inputs and len(changes_pics_inputs) > 0:
                combined_changes["changes_pics_inputs"] = changes_pics_inputs
            if changed_pics:
                combined_changes.setdefault("changed_pics", []).extend(changed_pics)
            if new_footnotes:
                toChangesFootnotes = []
                print("ids_saved_footnotes", ids_saved_footnotes)
                for id_saved_footnote in ids_saved_footnotes:   
                    print("id_saved_footnote", id_saved_footnote)                 
                    footNote = Mongo().connect("footnotes").find_one({"_id": ObjectId(id_saved_footnote)})
                    print("footNote", footNote)
                    if footNote:                        
                        toChangesFootnotes.append(footNote)
                
                combined_changes.setdefault("new_footnotes", []).extend(toChangesFootnotes)
            if new_bibliographies:
                combined_changes.setdefault("new_bibliographies", []).extend(new_bibliographies)
          
            if changes_footnotes and len(changes_footnotes) > 0:
                combined_changes["footnotes_data_changes"] = {"changes_footnotes":changes_footnotes,"before_update_footnotes":before_update_footnotes}
                
            if changes_bibliographies and len(changes_bibliographies) > 0:
                combined_changes["bibliographies_data_changes"] = {"changes_bibliographies":changes_bibliographies,"before_update_bibliographies":before_update_bibliographies}
            # Add timestamps and approval info to the changes
            if documents:
                combined_changes["documents"] = documents
            timestamped_changes =  AuditManager().add_timestampsResearch(
                combined_changes, user_id, research, is_new_research
            )
            
            # Insert the timestamped changes into the inventory changes collection
            
            
            ResearchChanges.insert_one(ResearchUpdatePayload(**timestamped_changes).model_dump())
            _ = Mongo().checkAndDropIfExistCollection("pieces_search_serialized")
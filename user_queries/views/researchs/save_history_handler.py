from hmac import new
from bson import ObjectId
from requests import session
from user_queries.driver_database.mongo import Mongo
from ..tools import AuditManager
from user_queries.shemas.research_update_payload import ResearchUpdatePayload
from user_queries.views.common.utils import get_research_id
from user_queries.dataclasses.research_history_changes import HistoryChangesContext

def save_history_changes(ctx: HistoryChangesContext):
        
        changes = ctx.changes
        data_pics = ctx.data_pics
        #changes_pics_inputs = ctx.changes_pics_inputs
        #changed_pics = ctx.changed_pics
        new_footnotes = ctx.new_footnotes
        ids_saved_footnotes = ctx.ids_saved_footnotes
        new_bibliographies = ctx.new_bibliographies
        changes_footnotes = ctx.changes_footnotes
        before_update_footnotes = ctx.before_update_footnotes
        changes_bibliographies = ctx.changes_bibliographies
        before_update_bibliographies = ctx.before_update_bibliographies
        documents = ctx.documents
        ResearchChanges = ctx.mongo.connect("research_changes_history")

        if any(
            isinstance(x, dict)
            for x in [
                changes,
                data_pics,
                #changes_pics_inputs,
                #changed_pics,
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
            research_id = get_research_id(ctx._id)
            print("research_id: ", research_id)
            # Combine changes into a single dictionary
            if research_id:                
                combined_changes["research_id"] = ObjectId(research_id)
            if changes:
                print("changes", changes)
                combined_changes["changes"] = changes
            
            print("data_pics", data_pics)
            if data_pics:
                combined_changes["data_pics"] = data_pics            

            #if changes_pics_inputs and len(changes_pics_inputs) > 0:
            #    combined_changes["changes_pics_inputs"] = changes_pics_inputs
            #if changed_pics:
            #    combined_changes.setdefault("changed_pics", []).extend(changed_pics)
            if new_footnotes:
                toChangesFootnotes = []
                print("ids_saved_footnotes", ids_saved_footnotes)
                for id_saved_footnote in ids_saved_footnotes:   
                    print("id_saved_footnote", id_saved_footnote)                 
                    footNote = ctx.mongo.connect("footnotes").find_one({"_id": ObjectId(id_saved_footnote)}, session=ctx.session)
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
                combined_changes, ctx.user_id, ctx.research, ctx.is_new_research
            )            
            # Insert the timestamped changes into the inventory changes collection            
            ResearchChanges.insert_one(ResearchUpdatePayload(**timestamped_changes ).model_dump(exclude_none=False), session=ctx.session)
            _ = ctx.mongo.checkAndDropIfExistCollection("pieces_search_serialized")
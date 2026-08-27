import json
import os
import shutil
import tempfile
from io import BytesIO
from unittest.mock import patch as mock_patch

from bson import ObjectId
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from user_queries.driver_database.mongo import Mongo
from user_queries.tests.helpers import (
    assign_permission_to_role,
    assign_role_to_user,
    create_authorized_user,
    create_test_permission,
    create_test_role,
    create_test_user,
    login_test_user,
    require_test_database,
    reset_test_database,
)


class MongoAPIIntegrationTests(SimpleTestCase):

    # Executed once before all tests in this class
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mongo = require_test_database()
        reset_test_database(cls.mongo)

    # Executed before each test method
    def setUp(self):
        reset_test_database(self.mongo)
        self.client = APIClient()
        self.temporary_upload_directory = tempfile.mkdtemp(
            prefix="mnemosine_api_tests_"
        )
        self.research_photo_directory = os.path.join(
            self.temporary_upload_directory, "research_photos"
        )
        self.research_thumbnail_directory = os.path.join(
            self.temporary_upload_directory, "research_thumbnails"
        )
        self.research_document_directory = os.path.join(
            self.temporary_upload_directory, "research_documents"
        )
        self.restoration_photo_directory = os.path.join(
            self.temporary_upload_directory, "restoration_photos"
        )
        self.restoration_thumbnail_directory = os.path.join(
            self.temporary_upload_directory, "restoration_thumbnails"
        )
        self.restoration_document_directory = os.path.join(
            self.temporary_upload_directory, "restoration_documents"
        )
        os.makedirs(self.research_photo_directory)
        os.makedirs(self.research_thumbnail_directory)
        os.makedirs(self.research_document_directory)
        os.makedirs(self.restoration_photo_directory)
        os.makedirs(self.restoration_thumbnail_directory)
        os.makedirs(self.restoration_document_directory)
        self.settings_override = override_settings(
            TEMPORARY_UPLOAD_DIRECTORY=self.temporary_upload_directory + os.sep,
            PHOTO_RESEARCH_PATH=self.research_photo_directory + os.sep,
            THUMBNAILS_RESEARCH_PATH=self.research_thumbnail_directory + os.sep,
            DOCUMENT_RESEARCH_PATH=self.research_document_directory + os.sep,
            PHOTO_RESTORATION_PATH=self.restoration_photo_directory + os.sep,
            THUMBNAILS_RESTORATION_PATH=(
                self.restoration_thumbnail_directory + os.sep
            ),
            DOCUMENT_RESTORATION_PATH=self.restoration_document_directory + os.sep,
        )
        self.settings_override.enable()

    def create_editable_inventory_piece(
        self,
        *,
        inventory_number="TEST-INVENTORY-EDIT-001",
        origin_number="TEST-ORIGIN-OLD",
        catalog_number="TEST-CATALOG-OLD",
        tags="TEST_TAG_OLD",
        description_inventory="TEST_DESCRIPTION_UNCHANGED",
    ):
        module = {
            "_id": ObjectId(),
            "name": "inventory",
            "deleted_at": None,
        }
        self.mongo.connect("modules").insert_one(module)

        piece = {
            "_id": ObjectId(),
            "inventory_number": inventory_number,
            "origin_number": origin_number,
            "catalog_number": catalog_number,
            "tags": tags,
            "description_inventory": description_inventory,
            "deleted_at": None,
        }
        self.mongo.connect("pieces").insert_one(piece)
        return piece, module

    @staticmethod
    def inventory_edit_payload(
        *,
        old_origin_number="TEST-ORIGIN-OLD",
        new_origin_number="TEST-ORIGIN-UPDATED",
        old_tags="TEST_TAG_OLD",
        new_tags="TEST_TAG_UPDATED",
    ):
        changes = {
            "origin_number": {
                "oldValue": old_origin_number,
                "newValue": new_origin_number,
            },
            "tags": {
                "oldValue": old_tags,
                "newValue": new_tags,
            },
        }
        return {
            "changes": json.dumps(changes),
            "changes_pics_inputs": json.dumps({}),
            "changes_docs_inputs": json.dumps({}),
            "changed_pics": json.dumps({}),
            "changed_docs": json.dumps({}),
            "PicsNew": json.dumps([]),
            "DocumentsNew": json.dumps([]),
        }

    def submit_inventory_edit(self, piece, access, payload=None):
        return self.client.post(
            f"/authenticated/inventory_query/edit/{piece['_id']}/",
            payload or self.inventory_edit_payload(),
            format="multipart",
            **self.authorization(access),
        )

    def create_research_piece(
        self,
        *,
        inventory_number="TEST-INVENTORY-RESEARCH-001",
    ):
        module = {
            "_id": ObjectId(),
            "name": "research",
            "deleted_at": None,
        }
        self.mongo.connect("modules").insert_one(module)

        piece = {
            "_id": ObjectId(),
            "inventory_number": inventory_number,
            "origin_number": "TEST-RESEARCH-ORIGIN",
            "catalog_number": "TEST-RESEARCH-CATALOG",
            "tags": "TEST_RESEARCH_PIECE",
            "deleted_at": None,
        }
        self.mongo.connect("pieces").insert_one(piece)
        return piece, module

    def create_restoration_piece(
        self,
        *,
        inventory_number="TEST-INVENTORY-RESTORATION-001",
    ):
        module = {
            "_id": ObjectId(),
            "name": "restoration",
            "deleted_at": None,
        }
        self.mongo.connect("modules").insert_one(module)

        piece = {
            "_id": ObjectId(),
            "inventory_number": inventory_number,
            "origin_number": "TEST-RESTORATION-ORIGIN",
            "catalog_number": "TEST-RESTORATION-CATALOG",
            "tags": "TEST_RESTORATION_PIECE",
            "deleted_at": None,
        }
        self.mongo.connect("pieces").insert_one(piece)
        return piece, module

    def create_restoration_responsible(self):
        catalog = {
            "_id": ObjectId(),
            "code": "responsible_restorer",
            "name": "TEST_RESTORATION_RESPONSIBLE_CATALOG",
            "deleted_at": None,
        }
        responsible = {
            "_id": ObjectId(),
            "catalog_id": catalog["_id"],
            "title": "TEST_RESTORATION_RESPONSIBLE",
            "deleted_at": None,
        }
        self.mongo.connect("catalogs").insert_one(catalog)
        self.mongo.connect("catalog_elements").insert_one(responsible)
        return responsible

    @staticmethod
    def restoration_create_payload(responsible_restorer):
        changes = {
            "preliminary_examination": {
                "oldValue": "",
                "newValue": "TEST-RESTORATION-EXAMINATION-ORIGINAL",
            },
            "treatment_description": {
                "oldValue": "",
                "newValue": "TEST-RESTORATION-TREATMENT-UNCHANGED",
            },
            "observations": {
                "oldValue": "",
                "newValue": "TEST-RESTORATION-OBSERVATIONS-ORIGINAL",
            },
            "responsible_restorer": {
                "oldValue": None,
                "newValue": str(responsible_restorer),
            },
        }
        return {
            "formDatachanges": json.dumps(changes),
            "PicsNew": json.dumps([]),
            "DocumentsNew": json.dumps([]),
        }

    @staticmethod
    def restoration_edit_payload():
        changes = {
            "preliminary_examination": {
                "oldValue": "TEST-RESTORATION-EXAMINATION-ORIGINAL",
                "newValue": "TEST-RESTORATION-EXAMINATION-UPDATED",
            },
            "observations": {
                "oldValue": "TEST-RESTORATION-OBSERVATIONS-ORIGINAL",
                "newValue": "TEST-RESTORATION-OBSERVATIONS-UPDATED",
            },
        }
        return {
            "formDatachanges": json.dumps(changes),
            "changedPicsInputs": json.dumps({}),
            "PicsNew": json.dumps([]),
            "ChangedPics": json.dumps({}),
            "changedDocs": json.dumps({}),
            "DocumentsNew": json.dumps([]),
        }

    def submit_restoration_create(self, piece, access, responsible_restorer):
        return self.client.post(
            f"/authenticated/piece_restorations/insert/{piece['_id']}/",
            self.restoration_create_payload(responsible_restorer),
            format="multipart",
            **self.authorization(access),
        )

    def submit_restoration_edit(self, piece, restoration, access):
        return self.client.patch(
            "/authenticated/piece_restorations/update/"
            f"{piece['_id']}/restoration/{restoration['_id']}/",
            self.restoration_edit_payload(),
            format="multipart",
            **self.authorization(access),
        )

    @staticmethod
    def restoration_empty_patch_payload():
        return {
            "formDatachanges": json.dumps({}),
            "changedPicsInputs": json.dumps({}),
            "PicsNew": json.dumps([]),
            "ChangedPics": json.dumps({}),
            "changedDocs": json.dumps({}),
            "DocumentsNew": json.dumps([]),
        }

    def submit_restoration_payload(self, piece, restoration, access, payload):
        return self.client.patch(
            "/authenticated/piece_restorations/update/"
            f"{piece['_id']}/restoration/{restoration['_id']}/",
            payload,
            format="multipart",
            **self.authorization(access),
        )

    @staticmethod
    def research_edit_payload(changes):
        return {
            "Changes": json.dumps(changes),
            "PicsNew": json.dumps([]),
            "ChangedPics": json.dumps({}),
            "ChangesPicsInputs": json.dumps([]),
            "NewFootnotes": json.dumps([]),
            "NewBibliographies": json.dumps([]),
            "ChangesBibliographies": json.dumps([]),
            "ChangesFootnotes": json.dumps([]),
            "DocumentsNew": json.dumps([]),
            "ChangesDocs": json.dumps([]),
        }

    def submit_research_edit(self, piece, access, changes):
        return self.client.patch(
            f"/authenticated/piece_researchs/edit/{piece['_id']}/",
            self.research_edit_payload(changes),
            format="multipart",
            **self.authorization(access),
        )

    def submit_research_payload(self, piece, access, payload):
        return self.client.patch(
            f"/authenticated/piece_researchs/edit/{piece['_id']}/",
            payload,
            format="multipart",
            **self.authorization(access),
        )

    def initialize_research(self, piece, access):
        response = self.submit_research_edit(
            piece,
            access,
            {
                "title": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-AUXILIARY-BASE",
                },
                "card": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-AUXILIARY-CARD",
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        research = self.mongo.connect("researchs").find_one(
            {"piece_id": piece["_id"]}
        )
        self.assertIsNotNone(research)
        return research

    def assert_research_parent_audit(self, before, after, user):
        self.assertEqual(after["_id"], before["_id"])
        self.assertEqual(after["piece_id"], before["piece_id"])
        self.assertEqual(after["created_by"], before["created_by"])
        self.assertEqual(after["created_at"], before["created_at"])
        self.assertEqual(after["updated_by"], user["_id"])
        self.assertIsNotNone(after["updated_at"])
        self.assertGreaterEqual(after["updated_at"], after["created_at"])

    @staticmethod
    def research_png_upload(filename="test-research-photograph.png"):
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(image_buffer, format="PNG")
        content = image_buffer.getvalue()
        return (
            SimpleUploadedFile(filename, content, content_type="image/png"),
            content,
        )


    # This method is a test method executed after the setUp method, and it tests the user query API endpoint
    def test_user_query_all_initial_code_returns_prepared_piece_and_new_code(self):
        user, password = create_authorized_user(["ver_inventario"])
        login_response, access = login_test_user(self.client, user, password)
        self.assertEqual(login_response.data["permissions"], ["ver_inventario"])

        piece_id = ObjectId()
        self.mongo.connect("pieces").insert_one(
            {
                "_id": piece_id,
                "inventory_number": "TEST-INVENTORY-GET-001",
                "origin_number": "TEST-ORIGIN-GET-001",
                "catalog_number": "TEST-CATALOG-GET-001",
                "tags": "TEST_USER_QUERY_ALL",
                "deleted_at": None,
            }
        )

        response = self.client.get(
            "/authenticated/user_query/0",
            **self.authorization(access),
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(set(response.data), {"query", "code", "query_duration"})
        self.assertIsInstance(response.data["query"], list)
        self.assertEqual(len(response.data["query"]), 1)
        returned_piece = response.data["query"][0]
        self.assertEqual(returned_piece["_id"], str(piece_id))
        self.assertEqual(returned_piece["inventory_number"], "TEST-INVENTORY-GET-001")
        self.assertEqual(returned_piece["tags"], "TEST_USER_QUERY_ALL")
        self.assertIsInstance(response.data["code"], str)
        self.assertEqual(len(response.data["code"]), 120)
        self.assertNotEqual(response.data["code"], "0")

        code_document = self.mongo.connect("pieces_search_serialized").find_one(
            {"_id": "1code"}
        )
        self.assertEqual(code_document["unique_code"], response.data["code"])

        not_modified = self.client.get(
            f"/authenticated/user_query/{response.data['code']}",
            **self.authorization(access),
        )
        self.assertEqual(not_modified.status_code, 304)
        self.assertFalse(not_modified.content)

    # This method is a test method executed after the setUp method, and it tests the inventory new API endpoint
    def test_inventory_new_persists_pending_inventory_record(self):
        user, password = create_authorized_user(["agregar_inventario"])
        login_response, access = login_test_user(self.client, user, password)
        self.assertEqual(login_response.data["permissions"], ["agregar_inventario"])

        image_bytes = b"TEST_INVENTORY_IMAGE"
        image = SimpleUploadedFile(
            "test_inventory.jpg",
            image_bytes,
            content_type="image/jpeg",
        )
        changes = {
            "inventory_number": {"newValue": "TEST-INVENTORY-POST-001"},
            "origin_number": {"newValue": "TEST-ORIGIN-POST-001"},
            "catalog_number": {"newValue": "TEST-CATALOG-POST-001"},
        }
        pictures = [
            {
                "photographer": "TEST_PHOTOGRAPHER",
                "photographed_at": "2026-08-26",
                "description": "TEST_INVENTORY_ITEM",
                "size": len(image_bytes),
                "mime_type": "image/jpeg",
            }
        ]

        response = self.client.post(
            "/authenticated/inventory_query/new/",
            {
                "changes": json.dumps(changes),
                "PicsNew": json.dumps(pictures),
                "DocumentsNew": json.dumps([]),
                "files[new_img_0]": image,
            },
            format="multipart",
            **self.authorization(access),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, "data saved")

        pending = self.mongo.connect("inventory_change_approvals").find_one(
            {"new_piece.inventory_number": "TEST-INVENTORY-POST-001"}
        )
        self.assertIsNotNone(pending)
        self.assertIsInstance(pending["created_by"], ObjectId)
        self.assertEqual(pending["new_piece"]["origin_number"], "TEST-ORIGIN-POST-001")
        self.assertEqual(pending["new_piece"]["catalog_number"], "TEST-CATALOG-POST-001")
        self.assertEqual(pending["created_by"], user["_id"])
        self.assertIsNone(pending["approved_rejected"])
        self.assertIsNone(pending["approved_rejected_by"])
        self.assertEqual(len(pending["new_pics"]), 1)
        self.assertEqual(pending["new_pics"][0]["description"], "TEST_INVENTORY_ITEM")
        self.assertEqual(pending["new_pics"][0]["mime_type"], "image/jpeg")
        temporary_file = os.path.join(
            self.temporary_upload_directory,
            pending["new_pics"][0]["file_name"],
        )
        self.assertTrue(os.path.isfile(temporary_file))
        self.assertEqual(self.mongo.connect("pieces").count_documents({}), 0)

    def test_inventory_edit_persists_pending_changes_and_preserves_piece(self):
        user, password = create_authorized_user(["editar_inventario"])
        login_response, access = login_test_user(self.client, user, password)
        self.assertEqual(login_response.data["permissions"], ["editar_inventario"])
        piece, module = self.create_editable_inventory_piece()

        response = self.submit_inventory_edit(piece, access)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, "is ok")

        pending = self.mongo.connect("inventory_change_approvals").find_one(
            {"piece_id": piece["_id"], "approved_rejected": None}
        )
        self.assertIsNotNone(pending)
        self.assertEqual(
            pending["origin_number"],
            {
                "oldValue": "TEST-ORIGIN-OLD",
                "newValue": "TEST-ORIGIN-UPDATED",
            },
        )
        self.assertEqual(
            pending["tags"],
            {"oldValue": "TEST_TAG_OLD", "newValue": "TEST_TAG_UPDATED"},
        )
        self.assertNotIn("inventory_number", pending)
        self.assertNotIn("catalog_number", pending)
        self.assertNotIn("description_inventory", pending)
        self.assertEqual(pending["created_by"], user["_id"])
        self.assertEqual(pending["changed_by_module_id"], module["_id"])
        self.assertIsNone(pending["approved_rejected"])
        self.assertIsNone(pending["approved_rejected_by"])
        self.assertIn("created_at", pending)
        self.assertIn("updated_at", pending)

        stored_piece = self.mongo.connect("pieces").find_one({"_id": piece["_id"]})
        self.assertEqual(stored_piece["origin_number"], "TEST-ORIGIN-OLD")
        self.assertEqual(stored_piece["tags"], "TEST_TAG_OLD")
        self.assertEqual(stored_piece["inventory_number"], "TEST-INVENTORY-EDIT-001")
        self.assertEqual(stored_piece["catalog_number"], "TEST-CATALOG-OLD")
        self.assertEqual(
            stored_piece["description_inventory"],
            "TEST_DESCRIPTION_UNCHANGED",
        )

    def test_inventory_edit_without_edit_permission_is_rejected(self):
        user, password = create_authorized_user(["ver_inventario"])
        login_response, access = login_test_user(self.client, user, password)
        self.assertEqual(login_response.data["permissions"], ["ver_inventario"])
        piece, _ = self.create_editable_inventory_piece()

        response = self.submit_inventory_edit(piece, access)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, "No tienes permiso para editar inventario")
        self.assertEqual(
            self.mongo.connect("inventory_change_approvals").count_documents({}),
            0,
        )
        stored_piece = self.mongo.connect("pieces").find_one({"_id": piece["_id"]})
        self.assertEqual(stored_piece["origin_number"], "TEST-ORIGIN-OLD")
        self.assertEqual(stored_piece["tags"], "TEST_TAG_OLD")

    def test_inventory_edit_approval_updates_piece_and_approval_audit(self):
        piece, module = self.create_editable_inventory_piece(
            inventory_number="TEST-INVENTORY-APPROVAL-001",
            catalog_number="TEST-CATALOG-UNCHANGED",
        )
        editor, editor_password = create_authorized_user(
            ["editar_inventario"],
            role_name="TEST_EDITOR_ROLE",
            role_numeric_id=1,
            permission_start_id=1,
            email="test_editor@example.com",
            username="TEST_EDITOR",
            user_numeric_id=1,
        )
        _, editor_access = login_test_user(self.client, editor, editor_password)
        edit_response = self.submit_inventory_edit(
            piece,
            editor_access,
            self.inventory_edit_payload(
                new_origin_number="TEST-ORIGIN-APPROVED",
                new_tags="TEST_TAG_APPROVED",
            ),
        )
        self.assertEqual(edit_response.status_code, 200)

        pending = self.mongo.connect("inventory_change_approvals").find_one(
            {"piece_id": piece["_id"], "approved_rejected": None}
        )
        self.assertIsNotNone(pending)

        approver, approver_password = create_authorized_user(
            ["autorizar_colecciones"],
            role_name="TEST_APPROVER_ROLE",
            role_numeric_id=2,
            permission_start_id=2,
            email="test_approver@example.com",
            username="TEST_APPROVER",
            user_numeric_id=2,
        )
        login_response, approver_access = login_test_user(
            self.client,
            approver,
            approver_password,
        )
        self.assertEqual(
            login_response.data["permissions"],
            ["autorizar_colecciones"],
        )

        approval_response = self.client.put(
            f"/authenticated/inventory_query/edit/{piece['_id']}/",
            {"isApproved": True},
            format="json",
            **self.authorization(approver_access),
        )

        self.assertEqual(approval_response.status_code, 200)
        self.assertEqual(approval_response.data, "piece updated")
        stored_piece = self.mongo.connect("pieces").find_one({"_id": piece["_id"]})
        self.assertEqual(stored_piece["origin_number"], "TEST-ORIGIN-APPROVED")
        self.assertEqual(stored_piece["tags"], "TEST_TAG_APPROVED")
        self.assertEqual(stored_piece["catalog_number"], "TEST-CATALOG-UNCHANGED")

        decided = self.mongo.connect("inventory_change_approvals").find_one(
            {"_id": pending["_id"]}
        )
        self.assertEqual(decided["approved_rejected"], "approved")
        self.assertIsInstance(decided["approved_rejected_by"], ObjectId)
        self.assertEqual(decided["approved_rejected_by"], approver["_id"])
        self.assertIsInstance(decided["created_by"], ObjectId)
        self.assertEqual(decided["created_by"], editor["_id"])
        self.assertEqual(decided["changed_by_module_id"], module["_id"])
        self.assertEqual(decided["created_at"], pending["created_at"])
        self.assertEqual(decided["updated_at"], pending["updated_at"])
        self.assertEqual(len(decided["piece_before_changes"]), 1)
        self.assertEqual(
            decided["piece_before_changes"][0]["origin_number"],
            "TEST-ORIGIN-OLD",
        )
        self.assertIsNone(
            self.mongo.connect("inventory_change_approvals").find_one(
                {"piece_id": piece["_id"], "approved_rejected": None}
            )
        )

    def test_inventory_edit_rejection_preserves_piece_and_records_reviewer(self):
        piece, _ = self.create_editable_inventory_piece(
            inventory_number="TEST-INVENTORY-REJECTION-001",
            catalog_number="TEST-CATALOG-UNCHANGED",
        )
        editor, editor_password = create_authorized_user(
            ["editar_inventario"],
            role_name="TEST_EDITOR_ROLE",
            role_numeric_id=1,
            permission_start_id=1,
            email="test_editor@example.com",
            username="TEST_EDITOR",
            user_numeric_id=1,
        )
        _, editor_access = login_test_user(self.client, editor, editor_password)
        edit_response = self.submit_inventory_edit(
            piece,
            editor_access,
            self.inventory_edit_payload(
                new_origin_number="TEST-ORIGIN-REJECTED",
                new_tags="TEST_TAG_REJECTED",
            ),
        )
        self.assertEqual(edit_response.status_code, 200)
        pending = self.mongo.connect("inventory_change_approvals").find_one(
            {"piece_id": piece["_id"], "approved_rejected": None}
        )

        reviewer, reviewer_password = create_authorized_user(
            ["autorizar_colecciones"],
            role_name="TEST_REVIEWER_ROLE",
            role_numeric_id=2,
            permission_start_id=2,
            email="test_reviewer@example.com",
            username="TEST_REVIEWER",
            user_numeric_id=2,
        )
        _, reviewer_access = login_test_user(
            self.client,
            reviewer,
            reviewer_password,
        )

        rejection_response = self.client.put(
            f"/authenticated/inventory_query/edit/{piece['_id']}/",
            {"isApproved": False},
            format="json",
            **self.authorization(reviewer_access),
        )

        self.assertEqual(rejection_response.status_code, 200)
        self.assertEqual(rejection_response.data, "piece rejected")
        stored_piece = self.mongo.connect("pieces").find_one({"_id": piece["_id"]})
        self.assertEqual(stored_piece["origin_number"], "TEST-ORIGIN-OLD")
        self.assertEqual(stored_piece["tags"], "TEST_TAG_OLD")
        self.assertEqual(stored_piece["catalog_number"], "TEST-CATALOG-UNCHANGED")

        decided = self.mongo.connect("inventory_change_approvals").find_one(
            {"_id": pending["_id"]}
        )
        self.assertEqual(decided["approved_rejected"], "rejected")
        self.assertIsInstance(decided["approved_rejected_by"], ObjectId)
        self.assertEqual(decided["approved_rejected_by"], reviewer["_id"])
        self.assertIsInstance(decided["created_by"], ObjectId)
        self.assertNotIn("piece_before_changes", decided)
        self.assertIsNone(
            self.mongo.connect("inventory_change_approvals").find_one(
                {"piece_id": piece["_id"], "approved_rejected": None}
            )
        )

    def test_inventory_edit_approval_without_permission_is_rejected(self):
        piece, _ = self.create_editable_inventory_piece(
            inventory_number="TEST-INVENTORY-UNAUTHORIZED-001",
            catalog_number="TEST-CATALOG-UNCHANGED",
        )
        editor, editor_password = create_authorized_user(
            ["editar_inventario"],
            role_name="TEST_EDITOR_ROLE",
            role_numeric_id=1,
            permission_start_id=1,
            email="test_editor@example.com",
            username="TEST_EDITOR",
            user_numeric_id=1,
        )
        _, editor_access = login_test_user(self.client, editor, editor_password)
        edit_response = self.submit_inventory_edit(
            piece,
            editor_access,
            self.inventory_edit_payload(
                new_origin_number="TEST-ORIGIN-UNAUTHORIZED",
                new_tags="TEST_TAG_UNAUTHORIZED",
            ),
        )
        self.assertEqual(edit_response.status_code, 200)
        pending = self.mongo.connect("inventory_change_approvals").find_one(
            {"piece_id": piece["_id"], "approved_rejected": None}
        )

        viewer, viewer_password = create_authorized_user(
            ["ver_inventario"],
            role_name="TEST_VIEWER_ROLE",
            role_numeric_id=2,
            permission_start_id=2,
            email="test_viewer@example.com",
            username="TEST_VIEWER",
            user_numeric_id=2,
        )
        _, viewer_access = login_test_user(self.client, viewer, viewer_password)

        response = self.client.put(
            f"/authenticated/inventory_query/edit/{piece['_id']}/",
            {"isApproved": True},
            format="json",
            **self.authorization(viewer_access),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            "No tienes permiso para autorizar cambios de inventario",
        )
        stored_piece = self.mongo.connect("pieces").find_one({"_id": piece["_id"]})
        self.assertEqual(stored_piece["origin_number"], "TEST-ORIGIN-OLD")
        self.assertEqual(stored_piece["tags"], "TEST_TAG_OLD")
        still_pending = self.mongo.connect("inventory_change_approvals").find_one(
            {"_id": pending["_id"]}
        )
        self.assertIsNone(still_pending["approved_rejected"])
        self.assertIsNone(still_pending["approved_rejected_by"])

    def test_research_edit_creates_research_for_piece_when_none_exists(self):
        user, password = create_authorized_user(["editar_investigacion"])
        login_response, access = login_test_user(self.client, user, password)
        self.assertEqual(
            login_response.data["permissions"],
            ["editar_investigacion"],
        )
        piece, _ = self.create_research_piece()
        self.assertEqual(
            self.mongo.connect("researchs").count_documents(
                {"piece_id": piece["_id"]}
            ),
            0,
        )

        response = self.submit_research_edit(
            piece,
            access,
            {
                "title": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-ORIGINAL",
                },
                "observation": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-OBSERVATION-ORIGINAL",
                },
                "card": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-CARD-UNCHANGED",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"ok": True, "message": "msg1ok"})
        researchs = list(
            self.mongo.connect("researchs").find({"piece_id": piece["_id"]})
        )
        self.assertEqual(len(researchs), 1)
        research = researchs[0]
        self.assertEqual(research["piece_id"], piece["_id"])
        self.assertEqual(research["title"], "TEST-RESEARCH-ORIGINAL")
        self.assertEqual(
            research["observation"],
            "TEST-RESEARCH-OBSERVATION-ORIGINAL",
        )
        self.assertEqual(research["card"], "TEST-RESEARCH-CARD-UNCHANGED")
        self.assertFalse(research["firm"])
        self.assertIsNone(research["materials"])
        self.assertEqual(research["created_by"], user["_id"])
        self.assertIsInstance(research["created_by"], ObjectId)
        self.assertIsNotNone(research["created_at"])
        self.assertIsNone(research["updated_by"])
        self.assertIsNone(research["updated_at"])

        history = self.mongo.connect("research_changes_history").find_one(
            {"research_id": research["_id"]}
        )
        self.assertIsNotNone(history)
        self.assertEqual(history["created_by"], user["_id"])
        self.assertEqual(
            history["changes"]["title"]["newValue"],
            "TEST-RESEARCH-ORIGINAL",
        )
        self.assertIn("research_before_update", history)
        self.assertIsNone(history["research_before_update"])
        self.assertNotIn("research_before_changes", history)

    def test_research_edit_updates_existing_research_without_duplicate(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-EDIT-001"
        )
        create_response = self.submit_research_edit(
            piece,
            access,
            {
                "title": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-ORIGINAL",
                },
                "observation": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-OBSERVATION-ORIGINAL",
                },
                "card": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-CARD-UNCHANGED",
                },
            },
        )
        self.assertEqual(create_response.status_code, 200)
        original = self.mongo.connect("researchs").find_one(
            {"piece_id": piece["_id"]}
        )

        update_response = self.submit_research_edit(
            piece,
            access,
            {
                "title": {
                    "oldValue": "TEST-RESEARCH-ORIGINAL",
                    "newValue": "TEST-RESEARCH-UPDATED",
                },
                "observation": {
                    "oldValue": "TEST-RESEARCH-OBSERVATION-ORIGINAL",
                    "newValue": "TEST-RESEARCH-OBSERVATION-UPDATED",
                },
            },
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(
            update_response.data,
            {"ok": True, "message": "msg1ok"},
        )
        self.assertEqual(
            self.mongo.connect("researchs").count_documents(
                {"piece_id": piece["_id"]}
            ),
            1,
        )
        updated = self.mongo.connect("researchs").find_one(
            {"piece_id": piece["_id"]}
        )
        self.assertEqual(updated["_id"], original["_id"])
        self.assertEqual(updated["piece_id"], piece["_id"])
        self.assertEqual(updated["title"], "TEST-RESEARCH-UPDATED")
        self.assertEqual(
            updated["observation"],
            "TEST-RESEARCH-OBSERVATION-UPDATED",
        )
        self.assertEqual(updated["card"], "TEST-RESEARCH-CARD-UNCHANGED")
        self.assertEqual(updated["created_by"], user["_id"])
        self.assertEqual(updated["created_at"], original["created_at"])
        self.assertEqual(updated["updated_by"], user["_id"])
        self.assertIsNotNone(updated["updated_at"])
        self.assertGreaterEqual(updated["updated_at"], updated["created_at"])
        self.assertEqual(
            self.mongo.connect("research_changes_history").count_documents(
                {"research_id": original["_id"]}
            ),
            2,
        )
        update_history = self.mongo.connect("research_changes_history").find_one(
            {
                "research_id": original["_id"],
                "changes.title.newValue": "TEST-RESEARCH-UPDATED",
            }
        )
        self.assertIsNotNone(update_history)
        self.assertIn("research_before_update", update_history)
        self.assertNotIn("research_before_changes", update_history)
        snapshot = update_history["research_before_update"]
        self.assertEqual(snapshot["_id"], original["_id"])
        self.assertEqual(snapshot["piece_id"], piece["_id"])
        self.assertEqual(snapshot["title"], "TEST-RESEARCH-ORIGINAL")
        self.assertEqual(snapshot["card"], "TEST-RESEARCH-CARD-UNCHANGED")

    def test_research_document_only_change_updates_parent_audit(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, module = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-DOCUMENT-001"
        )
        before = self.initialize_research(piece, access)
        history_count = self.mongo.connect(
            "research_changes_history"
        ).count_documents({"research_id": before["_id"]})
        document_content = b"TEST-RESEARCH-DOCUMENT-CONTENT"
        document_file = SimpleUploadedFile(
            "test-research-document.txt",
            document_content,
            content_type="text/plain",
        )
        payload = self.research_edit_payload({})
        payload["DocumentsNew"] = json.dumps(
            [{"name": "TEST-RESEARCH-DOCUMENT"}]
        )
        payload["files[new_doc_0]"] = document_file

        response = self.submit_research_payload(piece, access, payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"ok": True, "message": "msg1ok"})
        document = self.mongo.connect("documents").find_one(
            {
                "piece_id": piece["_id"],
                "module_id": module["_id"],
                "name": "TEST-RESEARCH-DOCUMENT",
            }
        )
        self.assertIsNotNone(document)
        self.assertEqual(document["size"], len(document_content))
        self.assertEqual(document["created_by"], user["_id"])
        after = self.mongo.connect("researchs").find_one({"_id": before["_id"]})
        self.assert_research_parent_audit(before, after, user)
        self.assertEqual(after["title"], before["title"])
        self.assertEqual(
            self.mongo.connect("research_changes_history").count_documents(
                {"research_id": before["_id"]}
            ),
            history_count + 1,
        )

    def test_research_bibliography_only_change_updates_parent_audit(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-BIBLIOGRAPHY-001"
        )
        before = self.initialize_research(piece, access)
        history_count = self.mongo.connect(
            "research_changes_history"
        ).count_documents({"research_id": before["_id"]})
        reference_type_id = ObjectId()
        payload = self.research_edit_payload({})
        payload["NewBibliographies"] = json.dumps(
            [
                {
                    "_id": None,
                    "reference_type_info": [{"_id": str(reference_type_id)}],
                    "title": "TEST-RESEARCH-BIBLIOGRAPHY",
                    "author": "TEST-RESEARCH-AUTHOR",
                }
            ]
        )

        response = self.submit_research_payload(piece, access, payload)

        self.assertEqual(response.status_code, 200)
        bibliography = self.mongo.connect("bibliographies").find_one(
            {
                "research_id": before["_id"],
                "title": "TEST-RESEARCH-BIBLIOGRAPHY",
            }
        )
        self.assertIsNotNone(bibliography)
        self.assertEqual(bibliography["reference_type_id"], reference_type_id)
        self.assertEqual(bibliography["created_by"], user["_id"])
        after = self.mongo.connect("researchs").find_one({"_id": before["_id"]})
        self.assert_research_parent_audit(before, after, user)
        self.assertEqual(after["card"], before["card"])
        self.assertEqual(
            self.mongo.connect("research_changes_history").count_documents(
                {"research_id": before["_id"]}
            ),
            history_count + 1,
        )

    def test_research_footnote_only_change_updates_parent_audit(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-FOOTNOTE-001"
        )
        before = self.initialize_research(piece, access)
        history_count = self.mongo.connect(
            "research_changes_history"
        ).count_documents({"research_id": before["_id"]})
        payload = self.research_edit_payload({})
        payload["NewFootnotes"] = json.dumps(
            [
                {
                    "_id": None,
                    "title": "TEST-RESEARCH-FOOTNOTE",
                    "description": "TEST-RESEARCH-FOOTNOTE-DESCRIPTION",
                }
            ]
        )

        response = self.submit_research_payload(piece, access, payload)

        self.assertEqual(response.status_code, 200)
        footnote = self.mongo.connect("footnotes").find_one(
            {
                "research_id": before["_id"],
                "title": "TEST-RESEARCH-FOOTNOTE",
            }
        )
        self.assertIsNotNone(footnote)
        self.assertEqual(
            footnote["description"],
            "TEST-RESEARCH-FOOTNOTE-DESCRIPTION",
        )
        self.assertEqual(footnote["created_by"], user["_id"])
        after = self.mongo.connect("researchs").find_one({"_id": before["_id"]})
        self.assert_research_parent_audit(before, after, user)
        self.assertEqual(after["title"], before["title"])
        self.assertEqual(
            self.mongo.connect("research_changes_history").count_documents(
                {"research_id": before["_id"]}
            ),
            history_count + 1,
        )

    def test_research_photograph_only_change_updates_parent_audit(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, module = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-PHOTOGRAPH-001"
        )
        before = self.initialize_research(piece, access)
        history_count = self.mongo.connect(
            "research_changes_history"
        ).count_documents({"research_id": before["_id"]})
        image_file, image_content = self.research_png_upload()
        payload = self.research_edit_payload({})
        payload["PicsNew"] = json.dumps(
            [
                {
                    "photographer": "TEST-RESEARCH-PHOTOGRAPHER",
                    "photographed_at": "2026-08-27T12:00:00",
                    "description": "TEST-RESEARCH-PHOTOGRAPH",
                    "size": len(image_content),
                    "mime_type": "image/png",
                }
            ]
        )
        payload["files[new_img_0]"] = image_file

        response = self.submit_research_payload(piece, access, payload)

        self.assertEqual(response.status_code, 200)
        photograph = self.mongo.connect("photographs").find_one(
            {
                "piece_id": piece["_id"],
                "module_id": module["_id"],
                "description": "TEST-RESEARCH-PHOTOGRAPH",
            }
        )
        self.assertIsNotNone(photograph)
        self.assertEqual(photograph["created_by"], user["_id"])
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.research_photo_directory,
                    photograph["file_name"],
                )
            )
        )
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.research_thumbnail_directory,
                    photograph["file_name"],
                )
            )
        )
        after = self.mongo.connect("researchs").find_one({"_id": before["_id"]})
        self.assert_research_parent_audit(before, after, user)
        self.assertEqual(after["card"], before["card"])
        self.assertEqual(
            self.mongo.connect("research_changes_history").count_documents(
                {"research_id": before["_id"]}
            ),
            history_count + 1,
        )

    def test_research_new_photograph_is_removed_after_later_failure(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-PHOTO-ROLLBACK-001"
        )
        research_before = self.initialize_research(piece, access)
        history_count = self.mongo.connect(
            "research_changes_history"
        ).count_documents({"research_id": research_before["_id"]})
        preexisting_photo = os.path.join(
            self.research_photo_directory, "preexisting-photo.keep"
        )
        preexisting_thumbnail = os.path.join(
            self.research_thumbnail_directory, "preexisting-thumbnail.keep"
        )
        with open(preexisting_photo, "xb") as file_handle:
            file_handle.write(b"PREEXISTING_PHOTO")
        with open(preexisting_thumbnail, "xb") as file_handle:
            file_handle.write(b"PREEXISTING_THUMBNAIL")
        image_file, image_content = self.research_png_upload(
            "test-research-photo-rollback.png"
        )
        payload = self.research_edit_payload({})
        payload["PicsNew"] = json.dumps(
            [
                {
                    "photographer": "TEST-ROLLBACK-PHOTOGRAPHER",
                    "photographed_at": "2026-08-27T12:00:00",
                    "description": "TEST-ROLLBACK-PHOTOGRAPH",
                    "size": len(image_content),
                    "mime_type": "image/png",
                }
            ]
        )
        payload["files[new_img_0]"] = image_file

        with mock_patch(
            "user_queries.views.research_views.save_history_changes",
            side_effect=RuntimeError("TEST_FAILURE_AFTER_PHOTO_WRITE"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "TEST_FAILURE_AFTER_PHOTO_WRITE"
            ):
                self.submit_research_payload(piece, access, payload)

        self.assertEqual(
            self.mongo.connect("photographs").count_documents(
                {"piece_id": piece["_id"]}
            ),
            0,
        )
        self.assertEqual(
            self.mongo.connect("researchs").find_one(
                {"_id": research_before["_id"]}
            ),
            research_before,
        )
        self.assertEqual(
            self.mongo.connect("research_changes_history").count_documents(
                {"research_id": research_before["_id"]}
            ),
            history_count,
        )
        self.assertEqual(os.listdir(self.research_photo_directory), ["preexisting-photo.keep"])
        self.assertEqual(
            os.listdir(self.research_thumbnail_directory),
            ["preexisting-thumbnail.keep"],
        )

    def test_research_new_document_is_removed_after_later_failure(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-DOCUMENT-ROLLBACK-001"
        )
        research_before = self.initialize_research(piece, access)
        history_count = self.mongo.connect(
            "research_changes_history"
        ).count_documents({"research_id": research_before["_id"]})
        preexisting_document = os.path.join(
            self.research_document_directory, "preexisting-document.keep"
        )
        with open(preexisting_document, "xb") as file_handle:
            file_handle.write(b"PREEXISTING_DOCUMENT")
        document_file = SimpleUploadedFile(
            "test-research-document-rollback.txt",
            b"TEST_DOCUMENT_CREATED_DURING_FAILED_REQUEST",
            content_type="text/plain",
        )
        payload = self.research_edit_payload({})
        payload["DocumentsNew"] = json.dumps(
            [{"name": "TEST-ROLLBACK-DOCUMENT"}]
        )
        payload["files[new_doc_0]"] = document_file

        with mock_patch(
            "user_queries.views.research_views.save_history_changes",
            side_effect=RuntimeError("TEST_FAILURE_AFTER_DOCUMENT_WRITE"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "TEST_FAILURE_AFTER_DOCUMENT_WRITE"
            ):
                self.submit_research_payload(piece, access, payload)

        self.assertEqual(
            self.mongo.connect("documents").count_documents(
                {"piece_id": piece["_id"]}
            ),
            0,
        )
        self.assertEqual(
            self.mongo.connect("researchs").find_one(
                {"_id": research_before["_id"]}
            ),
            research_before,
        )
        self.assertEqual(
            self.mongo.connect("research_changes_history").count_documents(
                {"research_id": research_before["_id"]}
            ),
            history_count,
        )
        self.assertEqual(
            os.listdir(self.research_document_directory),
            ["preexisting-document.keep"],
        )

    def test_research_photograph_replacement_restores_old_file_after_failure(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, module = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-PHOTO-REPLACE-001"
        )
        self.initialize_research(piece, access)
        original_file, original_content = self.research_png_upload(
            "test-research-photo-original.png"
        )
        create_payload = self.research_edit_payload({})
        create_payload["PicsNew"] = json.dumps(
            [
                {
                    "photographer": "TEST-ORIGINAL-PHOTOGRAPHER",
                    "photographed_at": "2026-08-27T12:00:00",
                    "description": "TEST-ORIGINAL-PHOTOGRAPH",
                    "size": len(original_content),
                    "mime_type": "image/png",
                }
            ]
        )
        create_payload["files[new_img_0]"] = original_file
        self.assertEqual(
            self.submit_research_payload(piece, access, create_payload).status_code,
            200,
        )
        photograph_before = self.mongo.connect("photographs").find_one(
            {"piece_id": piece["_id"], "module_id": module["_id"]}
        )
        research_before = self.mongo.connect("researchs").find_one(
            {"piece_id": piece["_id"]}
        )
        old_photo_path = os.path.join(
            self.research_photo_directory, photograph_before["file_name"]
        )
        old_thumbnail_path = os.path.join(
            self.research_thumbnail_directory, photograph_before["file_name"]
        )
        self.assertTrue(os.path.isfile(old_photo_path))
        self.assertTrue(os.path.isfile(old_thumbnail_path))
        replacement_file, _ = self.research_png_upload(
            "test-research-photo-replacement.png"
        )
        replace_payload = self.research_edit_payload({})
        replace_payload["ChangedPics"] = json.dumps(
            {"0": {"_id": str(photograph_before["_id"])}}
        )
        replace_payload["files[changed_img_0]"] = replacement_file

        with mock_patch(
            "user_queries.views.research_views.save_history_changes",
            side_effect=RuntimeError("TEST_FAILURE_AFTER_PHOTO_REPLACEMENT"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "TEST_FAILURE_AFTER_PHOTO_REPLACEMENT"
            ):
                self.submit_research_payload(piece, access, replace_payload)

        self.assertEqual(
            self.mongo.connect("photographs").find_one(
                {"_id": photograph_before["_id"]}
            ),
            photograph_before,
        )
        self.assertEqual(
            self.mongo.connect("researchs").find_one(
                {"_id": research_before["_id"]}
            ),
            research_before,
        )
        self.assertTrue(os.path.isfile(old_photo_path))
        self.assertTrue(os.path.isfile(old_thumbnail_path))
        self.assertFalse(
            os.path.exists(
                os.path.join(
                    self.research_photo_directory,
                    f"deleted_{photograph_before['file_name']}",
                )
            )
        )
        self.assertEqual(os.listdir(self.research_photo_directory), [photograph_before["file_name"]])
        self.assertEqual(
            os.listdir(self.research_thumbnail_directory),
            [photograph_before["file_name"]],
        )

    def test_research_document_replacement_restores_old_file_after_failure(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, module = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-DOC-REPLACE-001"
        )
        self.initialize_research(piece, access)
        original_document = SimpleUploadedFile(
            "test-research-document-original.txt",
            b"TEST_ORIGINAL_DOCUMENT",
            content_type="text/plain",
        )
        create_payload = self.research_edit_payload({})
        create_payload["DocumentsNew"] = json.dumps(
            [{"name": "TEST-ORIGINAL-DOCUMENT"}]
        )
        create_payload["files[new_doc_0]"] = original_document
        self.assertEqual(
            self.submit_research_payload(piece, access, create_payload).status_code,
            200,
        )
        document_before = self.mongo.connect("documents").find_one(
            {"piece_id": piece["_id"], "module_id": module["_id"]}
        )
        research_before = self.mongo.connect("researchs").find_one(
            {"piece_id": piece["_id"]}
        )
        old_document_path = os.path.join(
            self.research_document_directory, document_before["file_name"]
        )
        self.assertTrue(os.path.isfile(old_document_path))
        replacement_document = SimpleUploadedFile(
            "test-research-document-replacement.txt",
            b"TEST_REPLACEMENT_DOCUMENT",
            content_type="text/plain",
        )
        replace_payload = self.research_edit_payload({})
        replace_payload["ChangesDocs"] = json.dumps(
            {
                "0": {
                    "_id": str(document_before["_id"]),
                    "name": {
                        "oldValue": "TEST-ORIGINAL-DOCUMENT",
                        "newValue": "TEST-REPLACEMENT-DOCUMENT",
                    },
                }
            }
        )
        replace_payload["files[changed_doc_0]"] = replacement_document

        with mock_patch(
            "user_queries.views.research_views.save_history_changes",
            side_effect=RuntimeError("TEST_FAILURE_AFTER_DOCUMENT_REPLACEMENT"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "TEST_FAILURE_AFTER_DOCUMENT_REPLACEMENT"
            ):
                self.submit_research_payload(piece, access, replace_payload)

        self.assertEqual(
            self.mongo.connect("documents").find_one(
                {"_id": document_before["_id"]}
            ),
            document_before,
        )
        self.assertEqual(
            self.mongo.connect("researchs").find_one(
                {"_id": research_before["_id"]}
            ),
            research_before,
        )
        self.assertTrue(os.path.isfile(old_document_path))
        self.assertFalse(
            os.path.exists(
                os.path.join(
                    self.research_document_directory,
                    f"deleted_{document_before['file_name']}",
                )
            )
        )
        self.assertEqual(
            os.listdir(self.research_document_directory),
            [document_before["file_name"]],
        )

    def test_research_empty_patch_does_not_change_audit_or_history(self):
        user, password = create_authorized_user(["editar_investigacion"])
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-NOOP-001"
        )
        before = self.initialize_research(piece, access)
        history_count = self.mongo.connect(
            "research_changes_history"
        ).count_documents({"research_id": before["_id"]})

        response = self.submit_research_edit(piece, access, {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"ok": True, "message": "msg1ok"})
        after = self.mongo.connect("researchs").find_one({"_id": before["_id"]})
        self.assertEqual(after, before)
        self.assertEqual(
            self.mongo.connect("research_changes_history").count_documents(
                {"research_id": before["_id"]}
            ),
            history_count,
        )

    def test_research_edit_without_permission_cannot_create_or_update(self):
        viewer, viewer_password = create_authorized_user(["ver_investigacion"])
        viewer_login, viewer_access = login_test_user(
            self.client,
            viewer,
            viewer_password,
        )
        self.assertEqual(
            viewer_login.data["permissions"],
            ["ver_investigacion"],
        )
        piece, _ = self.create_research_piece(
            inventory_number="TEST-INVENTORY-RESEARCH-UNAUTHORIZED-001"
        )

        create_response = self.submit_research_edit(
            piece,
            viewer_access,
            {
                "title": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-UNAUTHORIZED",
                }
            },
        )

        self.assertEqual(create_response.status_code, 400)
        self.assertEqual(
            create_response.data,
            {
                "ok": False,
                "message": "No tienes permiso para crear investigaciones",
                "detail": "No tienes permiso para crear investigaciones",
            },
        )
        self.assertEqual(
            self.mongo.connect("researchs").count_documents(
                {"piece_id": piece["_id"]}
            ),
            0,
        )

        editor, editor_password = create_authorized_user(
            ["editar_investigacion"],
            role_name="TEST_RESEARCH_EDITOR_ROLE",
            role_numeric_id=2,
            permission_start_id=2,
            email="test_research_editor@example.com",
            username="TEST_RESEARCH_EDITOR",
            user_numeric_id=2,
        )
        _, editor_access = login_test_user(self.client, editor, editor_password)
        authorized_response = self.submit_research_edit(
            piece,
            editor_access,
            {
                "title": {
                    "oldValue": None,
                    "newValue": "TEST-RESEARCH-AUTHORIZED",
                }
            },
        )
        self.assertEqual(authorized_response.status_code, 200)
        stored_before_attempt = self.mongo.connect("researchs").find_one(
            {"piece_id": piece["_id"]}
        )

        update_response = self.submit_research_edit(
            piece,
            viewer_access,
            {
                "title": {
                    "oldValue": "TEST-RESEARCH-AUTHORIZED",
                    "newValue": "TEST-RESEARCH-UNAUTHORIZED-UPDATE",
                }
            },
        )

        self.assertEqual(update_response.status_code, 400)
        self.assertEqual(
            update_response.data,
            {
                "ok": False,
                "message": "No tienes permiso para editar investigaciones",
                "detail": "No tienes permiso para editar investigaciones",
            },
        )
        stored_after_attempt = self.mongo.connect("researchs").find_one(
            {"piece_id": piece["_id"]}
        )
        self.assertEqual(stored_after_attempt, stored_before_attempt)
        self.assertEqual(
            self.mongo.connect("research_changes_history").count_documents(
                {"research_id": stored_before_attempt["_id"]}
            ),
            1,
        )

    def test_restoration_create_persists_fields_and_initial_audit(self):
        user, password = create_authorized_user(["agregar_restauracion"])
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_restoration_piece()
        responsible_restorer = self.create_restoration_responsible()

        restorations = self.mongo.connect("restorations")
        self.assertEqual(restorations.count_documents({"piece_id": piece["_id"]}), 0)

        response = self.submit_restoration_create(
            piece, access, responsible_restorer["_id"]
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {})
        self.assertEqual(restorations.count_documents({"piece_id": piece["_id"]}), 1)
        restoration = restorations.find_one({"piece_id": piece["_id"]})
        self.assertIsInstance(restoration["_id"], ObjectId)
        self.assertEqual(restoration["piece_id"], piece["_id"])
        self.assertEqual(
            restoration["preliminary_examination"],
            "TEST-RESTORATION-EXAMINATION-ORIGINAL",
        )
        self.assertEqual(
            restoration["treatment_description"],
            "TEST-RESTORATION-TREATMENT-UNCHANGED",
        )
        self.assertEqual(
            restoration["observations"],
            "TEST-RESTORATION-OBSERVATIONS-ORIGINAL",
        )
        self.assertEqual(
            restoration["responsible_restorer"], responsible_restorer["_id"]
        )
        self.assertEqual(restoration["created_by"], user["_id"])
        self.assertIsNotNone(restoration["created_at"])
        self.assertIsNone(restoration["updated_by"])
        self.assertIsNone(restoration["updated_at"])
        self.assertIsNone(restoration["deleted_by"])
        self.assertIsNone(restoration["deleted_at"])
        self.assertEqual(restoration["photographs_ids"], [])
        self.assertEqual(restoration["documents_ids"], [])
        self.assertEqual(
            self.mongo.connect("restoration_changes_history").count_documents({}),
            0,
        )
        self.assertEqual(self.mongo.connect("photographs").count_documents({}), 0)
        self.assertEqual(self.mongo.connect("documents").count_documents({}), 0)

    def test_restoration_edit_updates_same_record_and_persists_history_snapshot(self):
        creator, creator_password = create_authorized_user(
            ["agregar_restauracion"],
            role_name="TEST_RESTORATION_CREATOR_ROLE",
            email="test_restoration_creator@example.com",
            username="TEST_RESTORATION_CREATOR",
        )
        _, creator_access = login_test_user(
            self.client, creator, creator_password
        )
        piece, _ = self.create_restoration_piece()
        responsible_restorer = self.create_restoration_responsible()
        create_response = self.submit_restoration_create(
            piece, creator_access, responsible_restorer["_id"]
        )
        self.assertEqual(create_response.status_code, 200)

        restorations = self.mongo.connect("restorations")
        before = restorations.find_one({"piece_id": piece["_id"]})
        self.assertIsNotNone(before)

        editor, editor_password = create_authorized_user(
            ["editar_restauracion"],
            role_name="TEST_RESTORATION_EDITOR_ROLE",
            role_numeric_id=2,
            permission_start_id=2,
            email="test_restoration_editor@example.com",
            username="TEST_RESTORATION_EDITOR",
            user_numeric_id=2,
        )
        _, editor_access = login_test_user(self.client, editor, editor_password)

        response = self.submit_restoration_edit(piece, before, editor_access)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"response": "Restauración actualizada"})
        self.assertEqual(restorations.count_documents({"piece_id": piece["_id"]}), 1)
        after = restorations.find_one({"_id": before["_id"]})
        self.assertEqual(after["_id"], before["_id"])
        self.assertEqual(after["piece_id"], before["piece_id"])
        self.assertEqual(
            after["preliminary_examination"],
            "TEST-RESTORATION-EXAMINATION-UPDATED",
        )
        self.assertEqual(
            after["observations"], "TEST-RESTORATION-OBSERVATIONS-UPDATED"
        )
        self.assertEqual(
            after["treatment_description"],
            "TEST-RESTORATION-TREATMENT-UNCHANGED",
        )
        self.assertEqual(after["created_by"], before["created_by"])
        self.assertEqual(after["created_at"], before["created_at"])
        self.assertEqual(after["updated_by"], editor["_id"])
        self.assertIsNotNone(after["updated_at"])
        self.assertGreaterEqual(after["updated_at"], after["created_at"])
        self.assertEqual(after["photographs_ids"], before["photographs_ids"])
        self.assertEqual(after["documents_ids"], before["documents_ids"])

        histories = list(
            self.mongo.connect("restoration_changes_history").find(
                {"restoration_id": before["_id"]}
            )
        )
        self.assertEqual(len(histories), 1)
        history = histories[0]
        self.assertEqual(history["piece_id"], piece["_id"])
        self.assertEqual(history["created_by"], editor["_id"])
        self.assertIsNotNone(history["created_at"])
        self.assertEqual(
            history["changes"]["preliminary_examination"]["newValue"],
            "TEST-RESTORATION-EXAMINATION-UPDATED",
        )
        snapshot = history["restoration_before_changes"]
        self.assertEqual(snapshot["_id"], before["_id"])
        self.assertEqual(snapshot["piece_id"], piece["_id"])
        self.assertEqual(
            snapshot["preliminary_examination"],
            "TEST-RESTORATION-EXAMINATION-ORIGINAL",
        )
        self.assertEqual(
            snapshot["treatment_description"],
            "TEST-RESTORATION-TREATMENT-UNCHANGED",
        )
        self.assertEqual(snapshot["created_by"], creator["_id"])
        self.assertEqual(snapshot["created_at"], before["created_at"])

    def test_restoration_create_without_permission_is_rejected_without_side_effects(self):
        user, password = create_authorized_user(["ver_restauracion"])
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_restoration_piece()

        response = self.submit_restoration_create(piece, access, ObjectId())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, "No tienes permiso para agregar restauraciones")
        self.assertEqual(self.mongo.connect("restorations").count_documents({}), 0)
        self.assertEqual(
            self.mongo.connect("restoration_changes_history").count_documents({}),
            0,
        )
        self.assertEqual(self.mongo.connect("photographs").count_documents({}), 0)
        self.assertEqual(self.mongo.connect("documents").count_documents({}), 0)

    def test_restoration_edit_without_permission_preserves_record_and_history(self):
        creator, creator_password = create_authorized_user(
            ["agregar_restauracion"],
            role_name="TEST_RESTORATION_CREATOR_ROLE",
            email="test_restoration_creator@example.com",
            username="TEST_RESTORATION_CREATOR",
        )
        _, creator_access = login_test_user(
            self.client, creator, creator_password
        )
        piece, _ = self.create_restoration_piece()
        responsible_restorer = self.create_restoration_responsible()
        self.assertEqual(
            self.submit_restoration_create(
                piece, creator_access, responsible_restorer["_id"]
            ).status_code,
            200,
        )
        restorations = self.mongo.connect("restorations")
        before = restorations.find_one({"piece_id": piece["_id"]})

        viewer, viewer_password = create_authorized_user(
            ["ver_restauracion"],
            role_name="TEST_RESTORATION_VIEWER_ROLE",
            role_numeric_id=2,
            permission_start_id=2,
            email="test_restoration_viewer@example.com",
            username="TEST_RESTORATION_VIEWER",
            user_numeric_id=2,
        )
        _, viewer_access = login_test_user(self.client, viewer, viewer_password)

        response = self.submit_restoration_edit(piece, before, viewer_access)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, "No tienes permiso para editar restauraciones")
        self.assertEqual(restorations.find_one({"_id": before["_id"]}), before)
        self.assertEqual(restorations.count_documents({"piece_id": piece["_id"]}), 1)
        self.assertEqual(
            self.mongo.connect("restoration_changes_history").count_documents({}),
            0,
        )
        self.assertEqual(self.mongo.connect("photographs").count_documents({}), 0)
        self.assertEqual(self.mongo.connect("documents").count_documents({}), 0)

    def test_restoration_create_with_document_persists_file_and_relationship(self):
        user, password = create_authorized_user(["agregar_restauracion"])
        _, access = login_test_user(self.client, user, password)
        piece, module = self.create_restoration_piece()
        responsible_restorer = self.create_restoration_responsible()
        document_content = b"TEST-RESTORATION-DOCUMENT-CONTENT"
        document_file = SimpleUploadedFile(
            "test-restoration-document.txt",
            document_content,
            content_type="text/plain",
        )
        payload = self.restoration_create_payload(responsible_restorer["_id"])
        payload["DocumentsNew"] = json.dumps(
            [{"name": "TEST-RESTORATION-DOCUMENT"}]
        )
        payload["files[new_doc_0]"] = document_file

        response = self.client.post(
            f"/authenticated/piece_restorations/insert/{piece['_id']}/",
            payload,
            format="multipart",
            **self.authorization(access),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {})
        documents = list(self.mongo.connect("documents").find({}))
        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertIsInstance(document["_id"], ObjectId)
        self.assertEqual(document["name"], "TEST-RESTORATION-DOCUMENT")
        self.assertEqual(document["piece_id"], piece["_id"])
        self.assertEqual(document["module_id"], module["_id"])
        self.assertEqual(document["size"], len(document_content))
        self.assertEqual(document["mime_type"], "text/plain")
        self.assertEqual(document["created_by"], user["_id"])
        stored_path = os.path.join(
            self.restoration_document_directory, document["file_name"]
        )
        self.assertTrue(os.path.isfile(stored_path))
        with open(stored_path, "rb") as stored_file:
            self.assertEqual(stored_file.read(), document_content)

        restoration = self.mongo.connect("restorations").find_one(
            {"piece_id": piece["_id"]}
        )
        self.assertEqual(restoration["documents_ids"], [document["_id"]])
        self.assertEqual(restoration["photographs_ids"], [])
        self.assertEqual(
            self.mongo.connect("restorations").count_documents(
                {"piece_id": piece["_id"]}
            ),
            1,
        )

    def test_restoration_patch_with_new_document_uses_shared_document_creation(self):
        user, password = create_authorized_user(
            ["agregar_restauracion", "editar_restauracion"]
        )
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_restoration_piece()
        responsible_restorer = self.create_restoration_responsible()
        self.assertEqual(
            self.submit_restoration_create(
                piece, access, responsible_restorer["_id"]
            ).status_code,
            200,
        )
        restoration = self.mongo.connect("restorations").find_one(
            {"piece_id": piece["_id"]}
        )
        document_content = b"TEST-RESTORATION-PATCH-DOCUMENT-CONTENT"
        document_file = SimpleUploadedFile(
            "test-restoration-patch-document.txt",
            document_content,
            content_type="text/plain",
        )
        payload = self.restoration_edit_payload()
        payload["DocumentsNew"] = json.dumps(
            [{"name": "TEST-RESTORATION-PATCH-DOCUMENT"}]
        )
        payload["files[new_doc_0]"] = document_file

        response = self.submit_restoration_payload(
            piece, restoration, access, payload
        )

        self.assertEqual(response.status_code, 200)
        documents = list(self.mongo.connect("documents").find({}))
        self.assertEqual(len(documents), 1)
        document = documents[0]
        updated_restoration = self.mongo.connect("restorations").find_one(
            {"_id": restoration["_id"]}
        )
        self.assertEqual(updated_restoration["documents_ids"], [document["_id"]])
        self.assertEqual(document["piece_id"], piece["_id"])
        self.assertEqual(document["name"], "TEST-RESTORATION-PATCH-DOCUMENT")
        self.assertEqual(document["size"], len(document_content))
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.restoration_document_directory, document["file_name"]
                )
            )
        )

    def test_restoration_empty_patch_does_not_change_audit_or_history(self):
        user, password = create_authorized_user(
            ["agregar_restauracion", "editar_restauracion"]
        )
        _, access = login_test_user(self.client, user, password)
        piece, _ = self.create_restoration_piece()
        responsible_restorer = self.create_restoration_responsible()
        self.assertEqual(
            self.submit_restoration_create(
                piece, access, responsible_restorer["_id"]
            ).status_code,
            200,
        )
        restorations = self.mongo.connect("restorations")
        before = restorations.find_one({"piece_id": piece["_id"]})
        history = self.mongo.connect("restoration_changes_history")
        history_count = history.count_documents({"restoration_id": before["_id"]})

        response = self.submit_restoration_payload(
            piece,
            before,
            access,
            self.restoration_empty_patch_payload(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"response": "Restauración actualizada"})
        after = restorations.find_one({"_id": before["_id"]})
        self.assertEqual(after, before)
        self.assertEqual(after["_id"], before["_id"])
        self.assertEqual(after["piece_id"], before["piece_id"])
        self.assertEqual(after["updated_by"], before["updated_by"])
        self.assertEqual(after["updated_at"], before["updated_at"])
        self.assertEqual(
            history.count_documents({"restoration_id": before["_id"]}),
            history_count,
        )
        self.assertEqual(self.mongo.connect("photographs").count_documents({}), 0)
        self.assertEqual(self.mongo.connect("documents").count_documents({}), 0)


    # This method is a test method executed after the setUp method, and it tests the inventory new API endpoint
    def test_protected_endpoint_without_jwt_is_rejected(self):
        response = self.client.post(
            "/authenticated/inventory_query/new/",
            {},
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"].code, "not_authenticated")
        self.assertEqual(
            str(response.data["detail"]),
            "Authentication credentials were not provided.",
        )
    # This method is a test method executed after the setUp method, and it tests a valid JWT without the required permission for the inventory new API endpoint
    def test_valid_jwt_without_required_permission_is_rejected(self):
        role = create_test_role()
        unrelated_permission = create_test_permission("ver_inventario", 1)
        assign_permission_to_role(role, unrelated_permission)
        user, password = create_test_user()
        assign_role_to_user(user, role)
        login_response, access = login_test_user(self.client, user, password)
        self.assertEqual(login_response.data["permissions"], ["ver_inventario"])

        response = self.client.post(
            "/authenticated/inventory_query/new/",
            {},
            format="multipart",
            **self.authorization(access),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, "No tienes permiso para agregar inventario")
        self.assertEqual(
            self.mongo.connect("inventory_change_approvals").count_documents({}),
            0,
        )



    # This method is executed after each test method
    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.temporary_upload_directory, ignore_errors=True)
        reset_test_database(self.mongo)

    # Executed once after all tests in this class    
    @classmethod
    def tearDownClass(cls):
        reset_test_database(cls.mongo)
        cls.mongo.client.close()
        super().tearDownClass()
         

    # This method is a static method that returns the authorization header for a given access token
    @staticmethod
    def authorization(access):
        return {"HTTP_AUTHORIZATION": f"Bearer {access}"}

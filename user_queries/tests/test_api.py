import json
import os
import shutil
import tempfile

from bson import ObjectId
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
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
        self.settings_override = override_settings(
            TEMPORARY_UPLOAD_DIRECTORY=self.temporary_upload_directory + os.sep
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
        self.assertEqual(decided["approved_rejected_by"], str(approver["_id"]))
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
        self.assertEqual(decided["approved_rejected_by"], str(reviewer["_id"]))
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

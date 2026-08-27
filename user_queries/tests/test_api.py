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



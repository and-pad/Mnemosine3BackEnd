from django.test import SimpleTestCase

from authentication.views import Permission
from user_queries.tests.helpers import (
    assign_permission_to_role,
    assign_permission_to_user,
    assign_role_to_user,
    create_test_permission,
    create_test_role,
    create_test_user,
    require_test_database,
    reset_test_database,
)


class PermissionIntegrationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mongo = require_test_database()
        reset_test_database(cls.mongo)

    @classmethod
    def tearDownClass(cls):
        reset_test_database(cls.mongo)
        cls.mongo.client.close()
        super().tearDownClass()

    def setUp(self):
        reset_test_database(self.mongo)

    def tearDown(self):
        reset_test_database(self.mongo)

    def test_combines_permissions_from_multiple_roles(self):
        permission_a = create_test_permission("permiso_a", 1)
        permission_b = create_test_permission("permiso_b", 2)
        role_a = create_test_role("TEST_ROLE_A", 1)
        role_b = create_test_role("TEST_ROLE_B", 2)
        assign_permission_to_role(role_a, permission_a)
        assign_permission_to_role(role_b, permission_b)
        user, _ = create_test_user()
        assign_role_to_user(user, role_a)
        assign_role_to_user(user, role_b)

        permissions = Permission().get_permission(user)

        self.assertCountEqual(permissions, ["permiso_a", "permiso_b"])
        self.assertEqual(len(permissions), len(set(permissions)))

    def test_deduplicates_permission_shared_by_multiple_roles(self):
        common_permission = create_test_permission("permiso_comun", 1)
        permission_a = create_test_permission("permiso_a", 2)
        permission_b = create_test_permission("permiso_b", 3)
        role_a = create_test_role("TEST_ROLE_A", 1)
        role_b = create_test_role("TEST_ROLE_B", 2)
        assign_permission_to_role(role_a, common_permission)
        assign_permission_to_role(role_a, permission_a)
        assign_permission_to_role(role_b, common_permission)
        assign_permission_to_role(role_b, permission_b)
        user, _ = create_test_user()
        assign_role_to_user(user, role_a)
        assign_role_to_user(user, role_b)

        permissions = Permission().get_permission(user)

        self.assertCountEqual(
            permissions,
            ["permiso_comun", "permiso_a", "permiso_b"],
        )
        self.assertEqual(permissions.count("permiso_comun"), 1)
        self.assertEqual(len(permissions), len(set(permissions)))

    def test_direct_permission_overwrites_same_id_without_losing_other_roles(self):
        base_permission = create_test_permission("permiso_base", 1)
        overwrite_permission = create_test_permission("permiso_overwrite", 1)
        permission_a = create_test_permission("permiso_a", 2)
        permission_b = create_test_permission("permiso_b", 3)
        role_a = create_test_role("TEST_ROLE_A", 1)
        role_b = create_test_role("TEST_ROLE_B", 2)
        assign_permission_to_role(role_a, base_permission)
        assign_permission_to_role(role_a, permission_a)
        assign_permission_to_role(role_b, base_permission)
        assign_permission_to_role(role_b, permission_b)
        user, _ = create_test_user()
        assign_role_to_user(user, role_a)
        assign_role_to_user(user, role_b)
        assign_permission_to_user(user, overwrite_permission)

        permissions = Permission().get_permission(user)

        self.assertCountEqual(
            permissions,
            ["permiso_overwrite", "permiso_a", "permiso_b"],
        )
        self.assertNotIn("permiso_base", permissions)
        self.assertEqual(permissions.count("permiso_overwrite"), 1)
        self.assertEqual(len(permissions), len(set(permissions)))

    def test_user_without_roles_returns_empty_list(self):
        user, _ = create_test_user()

        permissions = Permission().get_permission(user)

        self.assertEqual(permissions, [])

    def test_direct_permissions_require_user_model_type(self):
        valid_permission = create_test_permission("permiso_usuario", 1)
        other_model_permission = create_test_permission("permiso_otro_modelo", 2)
        role = create_test_role("TEST_ROLE", 1)
        user, _ = create_test_user()
        assign_role_to_user(user, role)
        assign_permission_to_user(user, valid_permission)
        assign_permission_to_user(
            user,
            other_model_permission,
            model_type="OtroModelo",
        )

        permissions = Permission().get_permission(user)

        self.assertIn("permiso_usuario", permissions)
        self.assertNotIn("permiso_otro_modelo", permissions)

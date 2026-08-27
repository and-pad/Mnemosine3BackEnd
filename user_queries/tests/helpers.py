from datetime import datetime, timezone

from bson import ObjectId

from authentication.views import SignupSerializer
from user_queries.driver_database.mongo import Mongo


TEST_DATABASE_NAME = "Mnemosine_test"
MODEL_TYPE_USER = "Mnemosine\\User"


def require_test_database(mongo=None):
    mongo = mongo or Mongo()
    if mongo.db_name != TEST_DATABASE_NAME:
        raise RuntimeError(
            "Integration tests may only modify Mnemosine_test. "
            f"Current Mongo database: {mongo.db_name!r}. Run with "
            "MONGO_DATABASE=Mnemosine_test."
        )
    return mongo


def reset_test_database(mongo=None):
    mongo = require_test_database(mongo)
    mongo.client.drop_database(TEST_DATABASE_NAME)


def create_test_permission(name, numeric_id):
    mongo = require_test_database()
    now = datetime.now(timezone.utc)
    permission = {
        "_id": ObjectId(),
        "id": numeric_id,
        "name": name,
        "guard_name": "web",
        "created_at": now,
        "updated_at": now,
    }
    mongo.connect("permissions").insert_one(permission)
    return permission


def create_test_role(name="TEST_ROLE", numeric_id=1):
    mongo = require_test_database()
    now = datetime.now(timezone.utc)
    role = {
        "_id": ObjectId(),
        "id": numeric_id,
        "name": name,
        "guard_name": "web",
        "created_at": now,
        "updated_at": now,
    }
    mongo.connect("roles").insert_one(role)
    return role


def assign_permission_to_role(role, permission):
    mongo = require_test_database()
    mongo.connect("role_has_permissions").insert_one(
        {
            "_id": ObjectId(),
            "role_id": role["_id"],
            "permission_id": permission["_id"],
        }
    )


def create_test_user(
    email="test_user@example.com",
    password="TEST_PASSWORD_2026!",
    username="TEST_USER",
    numeric_id=1,
):
    require_test_database()
    serializer = SignupSerializer(
        data={
            "id": numeric_id,
            "username": username,
            "email": email,
            "password": password,
        }
    )
    if not serializer.is_valid():
        raise AssertionError(f"Invalid test user: {serializer.errors}")
    serializer.save()

    user = Mongo().connect("authentication_my_user").find_one({"email": email})
    if not user:
        raise AssertionError("SignupSerializer did not persist the test user")
    return user, password


def assign_role_to_user(user, role):
    mongo = require_test_database()
    mongo.connect("user_has_roles").insert_one(
        {
            "_id": ObjectId(),
            "role_id": role["_id"],
            "model_type": MODEL_TYPE_USER,
            "model_id": user["_id"],
        }
    )


def assign_permission_to_user(user, permission, model_type=MODEL_TYPE_USER):
    mongo = require_test_database()
    mongo.connect("user_has_permissions").insert_one(
        {
            "_id": ObjectId(),
            "permission_id": permission["_id"],
            "model_type": model_type,
            "model_id": user["_id"],
        }
    )


def create_authorized_user(permission_names):
    role = create_test_role()
    for numeric_id, name in enumerate(permission_names, start=1):
        permission = create_test_permission(name, numeric_id)
        assign_permission_to_role(role, permission)
    user, password = create_test_user()
    assign_role_to_user(user, role)
    return user, password


def login_test_user(client, user, password):
    response = client.post(
        "/auth/signin/",
        {"email": user["email"], "password": password},
        format="json",
    )
    if response.status_code != 202:
        raise AssertionError(
            f"Real login failed with {response.status_code}: {response.data!r}"
        )
    access = response.data.get("access")
    if not access:
        raise AssertionError("Real login response did not include an access token")
    return response, access

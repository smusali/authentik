"""SCIM Group tests"""

from json import loads
from time import time

from django.test import TestCase
from jsonschema import validate
from requests_mock import Mocker

from authentik.blueprints.tests import apply_blueprint
from authentik.core.models import Application, Group, User
from authentik.lib.generators import generate_id
from authentik.providers.scim.clients.groups import SCIMGroupClient
from authentik.providers.scim.clients.users import SCIMUserClient
from authentik.providers.scim.models import (
    SCIMMapping,
    SCIMProvider,
    SCIMProviderGroup,
    SCIMProviderUser,
)
from authentik.tenants.models import Tenant


class SCIMGroupTests(TestCase):
    """SCIM Group tests"""

    @apply_blueprint("system/providers-scim.yaml")
    def setUp(self) -> None:
        Tenant.objects.update(avatars="none")
        # Delete all users and groups as the mocked HTTP responses only return one ID
        # which will cause errors with multiple users
        User.objects.all().exclude_anonymous().delete()
        Group.objects.all().delete()
        self.provider: SCIMProvider = SCIMProvider.objects.create(
            name=generate_id(),
            url="https://localhost",
            token=generate_id(),
        )
        self.app: Application = Application.objects.create(
            name=generate_id(),
            slug=generate_id(),
        )
        self.app.backchannel_providers.add(self.provider)
        self.provider.property_mappings.set(
            [SCIMMapping.objects.get(managed="goauthentik.io/providers/scim/user")]
        )
        self.provider.property_mappings_group.set(
            [SCIMMapping.objects.get(managed="goauthentik.io/providers/scim/group")]
        )

    @Mocker()
    def test_group_create(self, mock: Mocker):
        """Test group creation"""
        scim_id = generate_id()
        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_id,
            },
        )
        uid = generate_id()
        group = Group.objects.create(
            name=uid,
        )
        self.assertEqual(mock.call_count, 2)
        self.assertEqual(mock.request_history[0].method, "GET")
        self.assertEqual(mock.request_history[1].method, "POST")
        self.assertJSONEqual(
            mock.request_history[1].body,
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "externalId": str(group.pk),
                "displayName": group.name,
            },
        )

    @Mocker()
    def test_group_create_update(self, mock: Mocker):
        """Test group creation and update"""
        scim_id = generate_id()
        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_id,
            },
        )
        mock.put(
            "https://localhost/Groups",
            json={
                "id": scim_id,
            },
        )
        uid = generate_id()
        group = Group.objects.create(
            name=uid,
        )
        self.assertEqual(mock.call_count, 2)
        self.assertEqual(mock.request_history[0].method, "GET")
        self.assertEqual(mock.request_history[1].method, "POST")
        body = loads(mock.request_history[1].body)
        with open("schemas/scim-group.schema.json", encoding="utf-8") as schema:
            validate(body, loads(schema.read()))
        self.assertEqual(
            body,
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "externalId": str(group.pk),
                "displayName": group.name,
            },
        )
        group.save()
        self.assertEqual(mock.call_count, 4)
        self.assertEqual(mock.request_history[0].method, "GET")
        self.assertEqual(mock.request_history[1].method, "POST")
        self.assertEqual(mock.request_history[2].method, "GET")
        self.assertEqual(mock.request_history[3].method, "PUT")

    @Mocker()
    def test_group_create_delete(self, mock: Mocker):
        """Test group creation"""
        scim_id = generate_id()
        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_id,
            },
        )
        mock.delete(f"https://localhost/Groups/{scim_id}", status_code=204)
        uid = generate_id()
        group = Group.objects.create(
            name=uid,
        )
        self.assertEqual(mock.call_count, 2)
        self.assertEqual(mock.request_history[0].method, "GET")
        self.assertEqual(mock.request_history[1].method, "POST")
        self.assertJSONEqual(
            mock.request_history[1].body,
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "externalId": str(group.pk),
                "displayName": group.name,
            },
        )
        group.delete()
        self.assertEqual(mock.call_count, 4)
        self.assertEqual(mock.request_history[0].method, "GET")
        self.assertEqual(mock.request_history[3].method, "DELETE")
        self.assertEqual(mock.request_history[3].url, f"https://localhost/Groups/{scim_id}")

    @Mocker()
    def test_group_integer_ids(self, mock: Mocker):
        """Test group creation with integer IDs from SCIM provider"""
        # Use timestamp-based IDs to ensure uniqueness across test runs
        timestamp = int(time() * 1000)  # Microsecond precision for uniqueness
        scim_id = timestamp  # Integer ID from SCIM provider
        user_scim_id = timestamp + 1  # Integer user ID from SCIM provider

        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_id,  # Integer ID
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "testgroup",
            },
        )
        mock.post(
            "https://localhost/Users",
            json={
                "id": user_scim_id,  # Integer ID
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": "testuser",
            },
        )

        # Create user with unique name and sync to SCIM
        unique_username = f"testuser-{user_scim_id}"
        user = User.objects.create(username=unique_username, email=f"{unique_username}@example.com")

        # Clean up any existing SCIM entries for this user to avoid constraint violations
        SCIMProviderUser.objects.filter(user=user, provider=self.provider).delete()

        user_client = SCIMUserClient(self.provider)
        scim_user = user_client.create(user)

        # Create group with unique name and sync to SCIM
        unique_group_name = f"testgroup-{scim_id}"
        group = Group.objects.create(name=unique_group_name)

        # Clean up any existing SCIM entries for this group to avoid constraint violations
        SCIMProviderGroup.objects.filter(group=group, provider=self.provider).delete()

        group_client = SCIMGroupClient(self.provider)
        scim_group = group_client.create(group)

        # Verify that integer IDs are automatically converted to strings by Pydantic
        self.assertIsInstance(scim_user.scim_id, str)
        self.assertEqual(scim_user.scim_id, str(user_scim_id))
        self.assertIsInstance(scim_group.scim_id, str)
        self.assertEqual(scim_group.scim_id, str(scim_id))

    @Mocker()
    def test_group_member_integer_values(self, mock: Mocker):
        """Test group sync with integer member values from SCIM provider (issue #15533)"""
        # Use timestamp-based IDs to ensure uniqueness across test runs
        timestamp = int(time() * 1000)
        scim_group_id = str(timestamp)  # Convert to string for group ID
        # Integer member values from provider
        scim_user_ids = [timestamp + 100 + i for i in range(5)]

        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_group_id,
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "testgroup",
            },
        )
        # Mock the GET request that was failing in the original issue
        mock.get(
            f"https://localhost/Groups/{scim_group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": scim_group_id,
                "members": [
                    {"value": user_id, "display": f"USER{user_id}"} for user_id in scim_user_ids
                ],
                "displayName": "GROUP1",
                "externalId": f"test-{timestamp}",  # Unique external ID
                "meta": {
                    "resourceType": "Group",
                    "created": "2025-07-13T05:58:06+00:00",
                    "lastModified": "2025-07-13T09:07:28+00:00",
                    "location": f"https://localhost/Groups/{scim_group_id}",
                },
            },
        )
        # Mock PATCH request for group updates
        mock.patch(
            f"https://localhost/Groups/{scim_group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": scim_group_id,
                "members": [
                    {"value": str(user_id), "display": f"USER{user_id}"}
                    for user_id in scim_user_ids
                ],
                "displayName": "GROUP1",
                "externalId": f"test-{timestamp}",
                "meta": {
                    "resourceType": "Group",
                    "created": "2025-07-13T05:58:06+00:00",
                    "lastModified": "2025-07-13T09:07:28+00:00",
                    "location": f"https://localhost/Groups/{scim_group_id}",
                },
            },
        )

        # Create group with unique name
        group_name = f"testgroup-{timestamp}"
        group = Group.objects.create(name=group_name)

        # Clean up any existing SCIM objects first
        SCIMProviderGroup.objects.filter(provider=self.provider, group=group).delete()

        # This should not raise a ValidationError anymore
        client = SCIMGroupClient(self.provider)

        # Create the SCIM connection and test the problematic patch_compare_users method
        scim_group_obj = SCIMProviderGroup.objects.create(
            provider=self.provider, group=group, scim_id=scim_group_id, attributes={}
        )

        # This should not raise a ValidationError for integer member values
        result = client.patch_compare_users(group)

        # Verify the method completed successfully (returns None on success)
        self.assertIsNone(result)

        # Cleanup
        scim_group_obj.delete()
        group.delete()

    @Mocker()
    def test_group_create_exception_fallback(self, mock: Mocker):
        """Test group creation with exception fallback for ID validation"""
        timestamp = int(time() * 1000)
        scim_id = timestamp

        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        # Mock a response that will cause validation to fail
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_id,
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "testgroup",
                # Add invalid field to trigger validation error
                "invalid_field": "invalid_value",
            },
        )

        group = Group.objects.create(name=f"testgroup-{timestamp}")

        # Clean up any existing SCIM entries
        SCIMProviderGroup.objects.filter(group=group, provider=self.provider).delete()

        client = SCIMGroupClient(self.provider)
        scim_group = client.create(group)

        # Should fallback to raw response.get("id")
        self.assertIsInstance(scim_group.scim_id, str)
        self.assertEqual(scim_group.scim_id, str(scim_id))

        # Cleanup
        scim_group.delete()
        group.delete()

    @Mocker()
    def test_group_patch_compare_users_request_exception(self, mock: Mocker):
        """Test patch_compare_users when GET request fails"""
        timestamp = int(time() * 1000)
        scim_group_id = str(timestamp)

        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_group_id,
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "testgroup",
            },
        )
        # Mock GET request to fail
        mock.get(
            f"https://localhost/Groups/{scim_group_id}",
            status_code=500,
            json={"error": "Internal Server Error"},
        )

        group = Group.objects.create(name=f"testgroup-{timestamp}")

        # Clean up any existing SCIM entries
        SCIMProviderGroup.objects.filter(group=group, provider=self.provider).delete()

        client = SCIMGroupClient(self.provider)

        # Create the SCIM connection
        scim_group_obj = SCIMProviderGroup.objects.create(
            provider=self.provider, group=group, scim_id=scim_group_id, attributes={}
        )

        # Should handle the exception and return None
        result = client.patch_compare_users(group)
        self.assertIsNone(result)

        # Cleanup
        scim_group_obj.delete()
        group.delete()

    @Mocker()
    def test_group_patch_compare_users_validation_exception(self, mock: Mocker):
        """Test patch_compare_users when validation fails"""
        timestamp = int(time() * 1000)
        scim_group_id = str(timestamp)

        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_group_id,
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "testgroup",
            },
        )
        # Mock GET request to return invalid data
        mock.get(
            f"https://localhost/Groups/{scim_group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": scim_group_id,
                # Missing required fields to trigger validation error
                "invalid_field": "invalid_value",
            },
        )

        group = Group.objects.create(name=f"testgroup-{timestamp}")

        # Clean up any existing SCIM entry

        SCIMProviderGroup.objects.filter(group=group, provider=self.provider).delete()

        client = SCIMGroupClient(self.provider)

        # Create the SCIM connection
        scim_group_obj = SCIMProviderGroup.objects.create(
            provider=self.provider, group=group, scim_id=scim_group_id, attributes={}
        )

        # Should handle the validation exception and return None
        result = client.patch_compare_users(group)
        self.assertIsNone(result)

        # Cleanup
        scim_group_obj.delete()
        group.delete()

    @Mocker()
    def test_group_patch_compare_users_no_changes(self, mock: Mocker):
        """Test patch_compare_users when no changes are needed"""
        timestamp = int(time() * 1000)
        scim_group_id = str(timestamp)

        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_group_id,
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "testgroup",
            },
        )
        # Mock GET request to return group with no members
        mock.get(
            f"https://localhost/Groups/{scim_group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": scim_group_id,
                "members": [],
                "displayName": "testgroup",
            },
        )

        group = Group.objects.create(name=f"testgroup-{timestamp}")

        # Clean up any existing SCIM entries
        SCIMProviderGroup.objects.filter(group=group, provider=self.provider).delete()

        client = SCIMGroupClient(self.provider)

        # Create the SCIM connection
        scim_group_obj = SCIMProviderGroup.objects.create(
            provider=self.provider, group=group, scim_id=scim_group_id, attributes={}
        )

        # Should return None when no changes are needed
        result = client.patch_compare_users(group)
        self.assertIsNone(result)

        # Cleanup
        scim_group_obj.delete()
        group.delete()

    @Mocker()
    def test_group_patch_compare_users_with_changes(self, mock: Mocker):
        """Test patch_compare_users when changes are needed"""
        timestamp = int(time() * 1000)
        scim_group_id = str(timestamp)

        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_group_id,
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "testgroup",
            },
        )
        # Mock GET request to return group with existing members
        mock.get(
            f"https://localhost/Groups/{scim_group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": scim_group_id,
                "members": [
                    {"value": "existing_user_1", "display": "Existing User 1"},
                    {"value": "existing_user_2", "display": "Existing User 2"},
                ],
                "displayName": "testgroup",
            },
        )
        # Mock PATCH request for group updates
        mock.patch(
            f"https://localhost/Groups/{scim_group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": scim_group_id,
                "members": [
                    {"value": "new_user_1", "display": "New User 1"},
                ],
                "displayName": "testgroup",
            },
        )

        group = Group.objects.create(name=f"testgroup-{timestamp}")

        # Clean up any existing SCIM entries
        SCIMProviderGroup.objects.filter(group=group, provider=self.provider).delete()

        # Create a user and SCIM connection for it
        user = User.objects.create(
            username=f"new_user_1_{timestamp}", email=f"new_user_1_{timestamp}@example.com"
        )
        SCIMProviderUser.objects.create(
            provider=self.provider, user=user, scim_id="new_user_1", attributes={}
        )
        group.users.add(user)

        client = SCIMGroupClient(self.provider)

        # Create the SCIM connection
        scim_group_obj = SCIMProviderGroup.objects.create(
            provider=self.provider, group=group, scim_id=scim_group_id, attributes={}
        )

        # Should return the PATCH response when changes are needed
        result = client.patch_compare_users(group)
        self.assertIsNotNone(result)

        # Cleanup
        scim_group_obj.delete()
        group.delete()
        user.delete()

    @Mocker()
    def test_group_patch_compare_users_none_members(self, mock: Mocker):
        """Test patch_compare_users when current_group.members is None"""
        timestamp = int(time() * 1000)
        scim_group_id = str(timestamp)

        mock.get(
            "https://localhost/ServiceProviderConfig",
            json={},
        )
        mock.post(
            "https://localhost/Groups",
            json={
                "id": scim_group_id,
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "testgroup",
            },
        )
        # Mock GET request to return group with None members
        mock.get(
            f"https://localhost/Groups/{scim_group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": scim_group_id,
                "members": None,
                "displayName": "testgroup",
            },
        )

        group = Group.objects.create(name=f"testgroup-{timestamp}")

        # Clean up any existing SCIM entries
        SCIMProviderGroup.objects.filter(group=group, provider=self.provider).delete()

        client = SCIMGroupClient(self.provider)

        # Create the SCIM connection
        scim_group_obj = SCIMProviderGroup.objects.create(
            provider=self.provider, group=group, scim_id=scim_group_id, attributes={}
        )

        # Should handle None members gracefully
        result = client.patch_compare_users(group)
        self.assertIsNone(result)

        # Cleanup
        scim_group_obj.delete()
        group.delete()

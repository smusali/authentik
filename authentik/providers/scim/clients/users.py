"""User client"""

from django.db import transaction
from django.utils.http import urlencode
from pydantic import ValidationError

from authentik.core.models import User
from authentik.lib.sync.mapper import PropertyMappingManager
from authentik.lib.sync.outgoing.exceptions import ObjectExistsSyncException, StopSync
from authentik.policies.utils import delete_none_values
from authentik.providers.scim.clients.base import SCIMClient
from authentik.providers.scim.clients.schema import SCIM_USER_SCHEMA
from authentik.providers.scim.clients.schema import User as SCIMUserSchema
from authentik.providers.scim.models import SCIMMapping, SCIMProvider, SCIMProviderUser


class SCIMUserClient(SCIMClient[User, SCIMProviderUser, SCIMUserSchema]):
    """SCIM client for users"""

    connection_type = SCIMProviderUser
    connection_attr = "scimprovideruser_set"
    mapper: PropertyMappingManager

    def __init__(self, provider: SCIMProvider):
        super().__init__(provider)
        self.mapper = PropertyMappingManager(
            self.provider.property_mappings.all().order_by("name").select_subclasses(),
            SCIMMapping,
            ["provider", "connection"],
        )

    def to_schema(self, obj: User, connection: SCIMProviderUser) -> SCIMUserSchema:
        """Convert authentik user into SCIM"""
        raw_scim_user = super().to_schema(obj, connection)
        try:
            scim_user = SCIMUserSchema.model_validate(delete_none_values(raw_scim_user))
        except ValidationError as exc:
            raise StopSync(exc, obj) from exc
        if SCIM_USER_SCHEMA not in scim_user.schemas:
            scim_user.schemas.insert(0, SCIM_USER_SCHEMA)
        # As this might be unset, we need to tell pydantic it's set so ensure the schemas
        # are included, even if its just the defaults
        scim_user.schemas = list(scim_user.schemas)
        if not scim_user.externalId:
            scim_user.externalId = str(obj.uid)
        return scim_user

    def delete(self, obj: User):
        """Delete user"""
        scim_user = SCIMProviderUser.objects.filter(provider=self.provider, user=obj).first()
        if not scim_user:
            self.logger.debug("User does not exist in SCIM, skipping")
            return None
        response = self._request("DELETE", f"/Users/{scim_user.scim_id}")
        scim_user.delete()
        return response

    def create(self, user: User):
        """Create user from scratch and create a connection object"""
        scim_user = self.to_schema(user, None)
        with transaction.atomic():
            try:
                response = self._request(
                    "POST",
                    "/Users",
                    json=scim_user.model_dump(
                        mode="json",
                        exclude_unset=True,
                    ),
                )
            except ObjectExistsSyncException as exc:
                if not self._config.filter.supported:
                    raise exc
                users = self._request(
                    "GET", f"/Users?{urlencode({'filter': f'userName eq {scim_user.userName}'})}"
                )
                users_res = users.get("Resources", [])
                if len(users_res) < 1:
                    raise exc
                # Validate response through Pydantic schema to ensure ID coercion
                try:
                    scim_response = SCIMUserSchema.model_validate(users_res[0])
                    scim_id = scim_response.id
                except ValidationError as exc:
                    self.logger.warning("Failed to validate response as SCIM user", exc=exc)
                    # Fallback to raw response if validation fails
                    scim_id = users_res[0]["id"]
                return SCIMProviderUser.objects.create(
                    provider=self.provider,
                    user=user,
                    scim_id=scim_id,
                    attributes=users_res[0],
                )
            else:
                # Validate response through Pydantic schema to ensure ID coercion
                try:
                    scim_response = SCIMUserSchema.model_validate(response)
                    scim_id = scim_response.id
                except ValidationError as exc:
                    self.logger.warning("Failed to validate response as SCIM user", exc=exc)
                    # Fallback to raw response if validation fails
                    scim_id = response.get("id")

                if not scim_id or scim_id == "":
                    raise StopSync("SCIM Response with missing or invalid `id`")
                return SCIMProviderUser.objects.create(
                    provider=self.provider, user=user, scim_id=scim_id, attributes=response
                )

    def update(self, user: User, connection: SCIMProviderUser):
        """Update existing user"""
        scim_user = self.to_schema(user, connection)
        scim_user.id = connection.scim_id
        response = self._request(
            "PUT",
            f"/Users/{connection.scim_id}",
            json=scim_user.model_dump(
                mode="json",
                exclude_unset=True,
            ),
        )
        connection.attributes = response
        connection.save()

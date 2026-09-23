import strawberry

from lrb.accounts.selectors.get_current_user import get_current_user
from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.authorization.decorators import require_owner
from lrb.authorization.models.role import Role
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.core.graphql.errors import format_application_error
from lrb.core.graphql.payloads import SimpleMutationPayload, to_bulk_payload
from lrb.staff.graphql.inputs import (
    AcceptInvitationInput,
    BulkRevokeInvitationsInput,
    DemoteStaffFromLoginInput,
    InviteStaffInput,
    PromoteStaffToLoginInput,
    ResendInvitationInput,
    RevokeInvitationInput,
    SetStaffLoginAccessInput,
)
from lrb.staff.graphql.payloads import (
    AcceptInvitationPayload,
    BulkInvitationActionPayload,
    InvitationMutationPayload,
)
from lrb.staff.services.revoke_invitation import (
    revoke_invitation as revoke_invitation_action,
)
from lrb.staff.services.set_staff_login_access import (
    set_staff_login_access as set_staff_login_access_action,
)
from lrb.staff.services.resend_invitation import (
    resend_invitation as resend_invitation_action,
)
from lrb.staff.services.bulk_revoke_invitations import (
    bulk_revoke_invitations as bulk_revoke_invitations_action,
)
from lrb.staff.services.demote_staff_from_login import (
    demote_staff_from_login as demote_staff_from_login_action,
)
from lrb.staff.workflows.accept_invitation import (
    accept_invitation as accept_invitation_action,
)
from lrb.staff.workflows.invite_staff import invite_staff as invite_staff_action
from lrb.staff.workflows.promote_staff_to_login import (
    promote_staff_to_login as promote_staff_to_login_action,
)


@strawberry.type
class StaffMutation:
    @strawberry.mutation
    @require_owner()
    def invite_staff(
        self, info: strawberry.Info, input: InviteStaffInput
    ) -> InvitationMutationPayload:
        current = get_current_user(info)
        try:
            role = None
            if input.can_login and input.role_id:
                role = Role.objects.filter(
                    pk=input.role_id, company=current.company
                ).first()
                if not role:
                    raise ApplicationError(
                        message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND
                    )

            _, invitation = invite_staff_action(
                email=input.email,
                first_name=input.first_name,
                last_name=input.last_name,
                company=current.company,
                invited_by=current,
                request=info.context.request,
                can_login=input.can_login,
                role=role,
            )
            return InvitationMutationPayload(success=True, invitation=invitation)
        except ApplicationError as e:
            return InvitationMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def revoke_invitation(
        self, info: strawberry.Info, input: RevokeInvitationInput
    ) -> SimpleMutationPayload:
        try:
            revoke_invitation_action(invitation_id=input.invitation_id)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def resend_invitation(
        self, info: strawberry.Info, input: ResendInvitationInput
    ) -> InvitationMutationPayload:
        try:
            invitation = resend_invitation_action(
                invitation_id=input.invitation_id, request=info.context.request
            )
            return InvitationMutationPayload(success=True, invitation=invitation)
        except ApplicationError as e:
            return InvitationMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def set_staff_login_access(
        self, info: strawberry.Info, input: SetStaffLoginAccessInput
    ) -> SimpleMutationPayload:
        try:
            set_staff_login_access_action(
                user_id=input.user_id, can_login=input.can_login
            )
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def bulk_revoke_invitations(
        self, info: strawberry.Info, input: BulkRevokeInvitationsInput
    ) -> BulkInvitationActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_revoke_invitations_action(
            invitation_ids=input.invitation_ids, company_id=str(current.company_id)
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_owner()
    def demote_staff_from_login(
        self, info: strawberry.Info, input: DemoteStaffFromLoginInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            demote_staff_from_login_action(
                user_id=input.user_id, company_id=str(current.company_id)
            )
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def accept_invitation(
        self, info: strawberry.Info, input: AcceptInvitationInput
    ) -> AcceptInvitationPayload:
        try:
            user = accept_invitation_action(
                token=input.token, new_password=input.new_password
            )
            return AcceptInvitationPayload(success=True, user=user)
        except ApplicationError as e:
            return AcceptInvitationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner
    def promote_staff_to_login(
        self, info: strawberry.Info, input: PromoteStaffToLoginInput
    ) -> InvitationMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            role = Role.objects.filter(
                pk=input.role_id, company=str(current.company_id)
            ).first()
            if not role:
                raise ApplicationError(
                    message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND
                )

            _, invitation = promote_staff_to_login_action(
                user_id=input.user_id,
                company=current.company,
                role=role,
                invited_by=current,
                request=info.context.request,
            )
            return InvitationMutationPayload(success=True, invitation=invitation)
        except ApplicationError as e:
            return InvitationMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

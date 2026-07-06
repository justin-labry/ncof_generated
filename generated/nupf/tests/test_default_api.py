# coding: utf-8

from fastapi.testclient import TestClient


from pydantic import Field, StrictStr  # noqa: F401
from typing import Any, List  # noqa: F401
from typing_extensions import Annotated  # noqa: F401
from nupf.models.patch_item import PatchItem  # noqa: F401
from nupf.models.patch_result import PatchResult  # noqa: F401
from nupf.models.problem_details import ProblemDetails  # noqa: F401
from nupf.models.redirect_response import RedirectResponse  # noqa: F401


def test_delete_subscription(client: TestClient):
    """Test case for delete_subscription

    Nupf_EventExposure UnSubscribe service Operation
    """

    headers = {
        "Authorization": "Bearer special-key",
    }
    # uncomment below to make a request
    #response = client.request(
    #    "DELETE",
    #    "/ee-subscriptions/{subscriptionId}".format(subscriptionId='subscription_id_example'),
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_modify_subscription(client: TestClient):
    """Test case for modify_subscription

    Nupf_EventExposure Subscribe Modify service Operation
    """
    patch_item = [[nupf.PatchItem()]]

    headers = {
        "Authorization": "Bearer special-key",
    }
    # uncomment below to make a request
    #response = client.request(
    #    "PATCH",
    #    "/ee-subscriptions/{subscriptionId}".format(subscriptionId='subscription_id_example'),
    #    headers=headers,
    #    json=patch_item,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


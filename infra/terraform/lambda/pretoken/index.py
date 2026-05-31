"""Cognito Pre-Token-Generation (V2_0) trigger.

Copies the stable customer identity into the ACCESS token so the agent can read
it without relying on the ID token. Access-token claims are added WITHOUT the
`custom:` prefix.
"""


def handler(event, context):
    attrs = event["request"]["userAttributes"]
    claims = {}
    bank_customer_id = attrs.get("custom:bank_customer_id")
    if bank_customer_id:
        claims["bank_customer_id"] = bank_customer_id
    given_name = attrs.get("given_name")
    if given_name:
        claims["given_name"] = given_name
    event["response"] = {
        "claimsAndScopeOverrideDetails": {
            "accessTokenGeneration": {
                "claimsToAddOrOverride": claims,
            }
        }
    }
    return event

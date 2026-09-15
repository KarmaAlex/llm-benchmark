# Configuring Single Sign-On for the Internal Portal

This article walks through enabling SSO for the internal employee portal using the
company's identity provider.

## Steps

1. Open the admin console and navigate to the Authentication tab.
2. Enable the SAML 2.0 integration.
3. Upload the identity provider metadata file.
4. Assign the appropriate access groups.

## Troubleshooting

If users are redirected to an error page after login, check that the assertion
consumer service URL matches the one configured in the identity provider.

## See Also

- [Identity Provider Setup Guide](https://wiki.internal.example.com/idp-setup)
- [Access Group Management](https://wiki.internal.example.com/access-groups)
- [SSO Troubleshooting Runbook](https://runbooks.internal.example.com/sso-troubleshooting)
- [Portal Architecture Overview](https://wiki.internal.example.com/portal-architecture)

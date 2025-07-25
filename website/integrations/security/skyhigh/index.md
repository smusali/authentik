---
title: Integrate with Skyhigh Security
sidebar_label: Skyhigh Security
support_level: community
---

## What is Skyhigh Security

> Skyhigh Security is a Security Services Edge (SSE), Cloud Access Security Broker (CASB), and Secure Web Gateway (SWG), and Private Access (PA / ZTNA) cloud provider.
>
> -- https://www.skyhighsecurity.com/en-us/about.html

## Multiple Integration Points

Skyhigh has multiple points for SAML integration:

- Dashboard Administrator login - Allows you to manage the Skyhigh Security dashboard
- Web Gateway and Private access - Authenticates for Internet access and ZTNA/Private access

The following placeholder will be used throughout this document.

- `authentik.company` is the FQDN of the authentik installation.

:::note
This documentation lists only the settings that you need to change from their default values. Be aware that any changes other than those explicitly mentioned in this guide could cause issues accessing your application.
:::

## Integration for Dashboard Administrator login

### Configure Skyhigh Security

While logged in to your Skyhigh Security Dashboard, click the configuration gear and navigate to `User Management` -> `SAML Configuration` -> `Skyhigh Cloud Users` tab

Under the `Identity Provider` section enter the following values:

- Issuer: `https://authentik.company/skyhigh-dashboard`
- Certificate: Upload the signing certificate you will use for the Authentik provider
- Login URL: `https://authentik.company/application/saml/<application_slug>/sso/binding/init/`
- SP-Initiated Request Binding: HTTP-POST
- User exclusions: Select at least one administrator account to login directly (in case something goes wrong with SAML)

Press `Save`

Note the Audience and ACS URLs that appear. You will use these to configure Authentik below

### Configure Authentik

In the Authentik admin Interface, navigate to `Applications` -> `Providers`. Create a SAML provider with the following parameters:

- ACS URL: Enter the ACS URL provided by the Skyhigh Dashboard above
- Issuer: `https://authentik.company/skyhigh-dashboard`
- Service Provider Binding: `Post`
- Audience: Enter the Audience URL provided by the Skyhigh Dashboard above
- Signing certificate: Select the certificate you uploaded to Skyhigh above
- Property mappings: Select all default mappings.
- NameID Property Mapping: `Authentik default SAML Mapping: Email`

Create an application linked to this new provider and use the slug name you used in the Skyhigh section above.

## Integration for Web Gateway and Private Access

### Configure Authentik

In the Authentik admin Interface, navigate to `Applications` -> `Providers`. Create a SAML provider with the following parameters:

- ACS URL: `https://login.auth.ui.trellix.com/sso/saml2`
- Issuer: `https://authentik.company/skyhigh-swg`
- Service Provider Binding: `Post`
- Audience: `https://login.auth.ui.trellix.com/sso/saml2`
- Signing certificate: Select any certificate
- Property mappings: Select all default mappings.

Create an application linked to this new provider and note the name of its slug.

### Configure Skyhigh Security

While logged in to your Skyhigh Security Dashboard, click the configuration gear and navigate to `Infrastructure` -> `Web Gateway Setup`.

Under the `Setup SAML` section click the `New SAML` button.

Configure your SAML provider as follows:

- SAML Configuration Name: Enter a descriptive name here
- Service Provider Entity ID: `https://login.auth.ui.trellix.com/sso/saml2`
- SAML Identity Provider URL: `https://authentik.company/application/saml/<application_slug>/sso/binding/post/`
- Identity Provider Entity ID: `https://authentik.company/skyhigh-swg`
- User ID Attribute in SAML Response: `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress`
- Group ID Attribute in SAML Response: `http://schemas.xmlsoap.org/claims/Group`
- Identity Provider Certificate: Upload the certificate you selected in the Authentik SAML provider you created earlier
- Domain(s): Enter the email domain(s) you wish to redirect for authentication to Authentik

Save your changes and publish the web policy.

:::note
You must also ensure that your web and/or private access policies grant access to users who will be authenticated. This configuration is out of scope for this document.
:::

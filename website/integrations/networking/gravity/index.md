---
title: Integrate with Gravity
sidebar_label: Gravity
support_level: community
---

## What is Gravity

> Gravity is a fully-replicated DNS, DHCP, and TFTP server powered by [etcd](https://etcd.io/), offering features like built-in caching, ad/privacy blocking, automatic DNS registration, and metric tracking.
>
> -- https://gravity.beryju.io/

## Preparation

The following placeholders are used in this guide:

- `gravity.company` is the FQDN of the Gravity installation.
- `authentik.company` is the FQDN of the authentik installation.

:::note
This documentation lists only the settings that you need to change from their default values. Be aware that any changes other than those explicitly mentioned in this guide could cause issues accessing your application.
:::

:::note
Gravity automatically triggers SSO authentication when configured. To prevent this behavior, log in using the following URL: `https://gravity.company/ui/?local`.
:::

## authentik configuration

To support the integration of Gravity with authentik, you need to create an application/provider pair in authentik.

### Create an application and provider in authentik

1. Log in to authentik as an administrator and open the authentik Admin interface.
2. Navigate to **Applications** > **Applications** and click **Create with Provider** to create an application and provider pair. (Alternatively you can first create a provider separately, then create the application and connect it with the provider.)

- **Application**: Provide a descriptive name, an optional group for the type of application, the policy engine mode, and optional UI settings.
- **Choose a Provider type**: Select **OAuth2/OpenID Connect** as the provider type.
- **Configure the Provider**: Provide a name (or accept the auto-provided name), choose the authorization flow for this provider, and configure the following required settings:
    - Note the **Client ID**, **Client Secret**, and **slug** values because they will be required later.
    - Set a `Strict` redirect URI to `https://gravity.company/auth/oidc/callback`.
    - Select any available signing key.
- **Configure Bindings** _(optional)_: Create a [binding](/docs/add-secure-apps/flows-stages/bindings/) (policy, group, or user) to manage the listing and access to applications on a user's **My applications** page.

3. Click **Submit** to save the new application and provider.

## Gravity configuration

1. From the **Gravity administrative interface**, navigate to **Cluster** > **Roles** and click **API**.
2. Under the **OIDC** sub-section, configure the following values:

- **Issuer**: `https://authentik.company/application/o/<application_slug>/`
- **Client ID**: Your Client ID from authentik
- **Client Secret**: Your Client Secret from authentik
- **Redirect URL**: `https://gravity.company/auth/oidc/callback`

3. Click **Update** to save and apply your configuration.

## Configuration verification

To verify integration with authentik, log out of Gravity and attempt to visit the login page. You should be automatically redirected to authentik.

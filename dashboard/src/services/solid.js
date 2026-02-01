import {
    login,
    handleIncomingRedirect,
    getDefaultSession,
    fetch
} from "@inrupt/solid-client-authn-browser";
import {
    getSolidDataset,
    getThing,
    getStringNoLocale,
    getUrlAll
} from "@inrupt/solid-client";

export const auth = {
    login: async (oidcIssuer) => {
        if (!oidcIssuer) throw new Error("No OIDC issuer provided");
        await login({
            oidcIssuer,
            redirectUrl: window.location.href,
            clientName: "proxion-keyring Dashboard"
        });
    },

    handleRedirect: async () => {
        await handleIncomingRedirect();
        return getDefaultSession();
    },

    getSession: () => {
        return getDefaultSession();
    },

    logout: async () => {
        await getDefaultSession().logout();
    }
};

export const data = {
    getTunnels: async (podRoot) => {
        // Placeholder: Fetch from storage/proxion-keyring/tunnels.ttl or similar
        // For now returning mock data until data structure is defined
        return [
            { id: "tunnel-1", ip: "10.0.0.3/32", status: "Active" },
        ];
    }
};
